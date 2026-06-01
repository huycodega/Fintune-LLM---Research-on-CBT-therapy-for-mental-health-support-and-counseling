"""
Modal LLM service — Huysun29/cbt-llama-3.1-8b
(Llama-3.1-8B Instruct + CBT LoRA adapter)

Endpoints used by backend/app/services/llm_client.py:
    POST /generate   { messages, n_responses, temperature, top_p,
                        max_new_tokens } → { responses, timing }
    GET  /health     → { status, model, gpu }

Deploy:
    pip install modal
    modal token new                # one-time
    modal deploy modal/llm_service.py

After deploy, Modal prints two HTTPS URLs. Add them to your .env:
    MODAL_LLM_ENDPOINT=https://<workspace>--cbt-llm-generate.modal.run
    MODAL_HEALTH_ENDPOINT=https://<workspace>--cbt-llm-health.modal.run
    MOCK_LLM=false

Notes
-----
- Llama 3.1 uses a native system role — no message merging needed.
- flash_attention_2 is available on A10G (ampere+); enabled via
  attn_implementation="flash_attention_2" for ~2× throughput.
- HF_TOKEN is required because Meta-Llama-3.1-8B-Instruct is gated.
  Create a modal secret named "hf-secret" with key HF_TOKEN.
"""
import os
import time

import modal

# ─────────────────────────────────────────────────────────────────────────────
# Container image: CUDA + transformers + peft (LoRA merge)
# ─────────────────────────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "transformers==4.45.2",
        "peft==0.13.2",
        "accelerate==1.0.1",
        "huggingface-hub==0.25.2",
        "fastapi==0.115.0",
        "pydantic==2.9.2",
        "flash-attn==2.7.2.post1",  # A10G / H100 ampere+ only
    )
    .run_commands("pip install flash-attn --no-build-isolation || true")
)

app = modal.App("cbt-llm")

HF_REPO = os.environ.get("HF_MODEL_REPO", "Huysun29/cbt-llama-3.1-8b")
HF_BASE = os.environ.get("HF_BASE_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")

hf_secret = modal.Secret.from_name("hf-secret", required_keys=["HF_TOKEN"])


# ─────────────────────────────────────────────────────────────────────────────
# Modal class: loads models once per cold-start, stays warm 5 min
# ─────────────────────────────────────────────────────────────────────────────
@app.cls(
    gpu="A10G",                    # 24 GB VRAM — sufficient for 8B bf16 + LoRA
    image=image,
    secrets=[hf_secret],
    container_idle_timeout=300,
    timeout=900,
)
class CBTLLMService:
    @modal.enter()
    def load(self):
        """Run once per cold start — download base + attach LoRA adapter."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        from huggingface_hub import login

        login(os.environ["HF_TOKEN"])

        print(f"Loading base model: {HF_BASE}")
        self.tokenizer = AutoTokenizer.from_pretrained(HF_BASE)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Try flash-attn; fall back to sdpa (still fast on A10G)
        for attn_impl in ("flash_attention_2", "sdpa", "eager"):
            try:
                base = AutoModelForCausalLM.from_pretrained(
                    HF_BASE,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                    attn_implementation=attn_impl,
                )
                print(f"Base loaded with attn={attn_impl}")
                break
            except Exception as e:
                print(f"attn={attn_impl} failed ({e}), trying next")

        print(f"Attaching LoRA adapter: {HF_REPO}")
        self.model = PeftModel.from_pretrained(base, HF_REPO)
        self.model.eval()
        print("CBT Llama-3.1-8B ready.")

    @modal.method()
    def generate(self, messages: list, n_responses: int = 3,
                  temperature: float = 0.8, top_p: float = 0.9,
                  max_new_tokens: int = 400) -> dict:
        import torch
        t0 = time.time()

        # Llama 3.1 natively supports the system role — pass messages directly
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)

        inputs = self.tokenizer(
            prompt, return_tensors="pt",
            truncation=True, max_length=4096,
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                num_return_sequences=n_responses,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        prompt_len = inputs["input_ids"].shape[1]
        responses = [
            self.tokenizer.decode(
                seq[prompt_len:], skip_special_tokens=True).strip()
            for seq in outputs
        ]
        total = time.time() - t0
        return {
            "responses": responses,
            "timing": {
                "total_seconds": total,
                "per_response_seconds": total / max(n_responses, 1),
            },
            "mode": "modal",
            "model": HF_REPO,
        }


# ─────────────────────────────────────────────────────────────────────────────
# HTTP endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def generate(body: dict):
    """POST /generate"""
    svc = CBTLLMService()
    return svc.generate.remote(
        messages=body.get("messages", []),
        n_responses=int(body.get("n_responses", 3)),
        temperature=float(body.get("temperature", 0.8)),
        top_p=float(body.get("top_p", 0.9)),
        max_new_tokens=int(body.get("max_new_tokens", 400)),
    )


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def health():
    """GET /health"""
    return {
        "status": "ok",
        "model": HF_REPO,
        "base": HF_BASE,
        "role": "primary_responder",
    }
