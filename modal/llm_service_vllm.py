"""
Modal LLM service (vLLM engine) — Huysun29/cbt-qwen2.5-7b-v2

Drop-in replacement for llm_service.py with the SAME HTTP contract, so the
backend needs zero code changes — only the two endpoint env vars:

    POST /generate   { messages, n_responses, temperature, top_p,
                        max_new_tokens } → { responses, timing, mode, model }
    GET  /health     → { status, model, engine }

Why vLLM here
-------------
- The pipeline asks for n=3 drafts per turn: vLLM's parallel sampling (n in
  SamplingParams) generates them together instead of transformers'
  num_return_sequences slog → the single biggest latency win.
- PagedAttention → much better token throughput on the same GPU.
- 7B bf16 (~15 GB) fits an A10G/L4 24 GB — no A100 (and no credit-card gate
  on fresh Modal workspaces). MODAL_GPU env overrides if you want A100 back.

Deploy (on the workspace of your choice):
    modal profile activate huycodega        # or your workspace
    modal secret create huggingface HF_TOKEN=hf_xxx   # once per workspace
    modal deploy modal/llm_service_vllm.py

Then point Railway at it (explicit env beats the derived defaults):
    MODAL_LLM_ENDPOINT=https://<workspace>--cbt-vllm-generate.modal.run
    MODAL_HEALTH_ENDPOINT=https://<workspace>--cbt-vllm-health.modal.run

Notes
-----
- First cold start on a fresh workspace downloads the weights into the
  `cbt-model-cache` volume (one-time, ~5-10 min). After that a cold boot is
  engine init + load from volume.
- VLLM_EAGER=1 (default) skips CUDA-graph capture → faster cold boots at a
  small decode-throughput cost. Set VLLM_EAGER=0 once you run keep-warm.
"""
import os
import time

import modal

# ─────────────────────────────────────────────────────────────────────────────
# Image: vLLM wheels bundle their own CUDA-enabled torch.
# ─────────────────────────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.9.1",
        "huggingface-hub==0.33.0",
        "hf_transfer==0.1.9",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("cbt-vllm")

HF_REPO = os.environ.get("HF_MODEL_REPO", "Huysun29/cbt-qwen2.5-7b-v2")
GPU = os.environ.get("MODAL_GPU", "A10G")
# eager = no CUDA-graph capture: boots faster, decodes slightly slower.
ENFORCE_EAGER = os.environ.get("VLLM_EAGER", "1").lower() not in ("0", "false")
MAX_MODEL_LEN = int(os.environ.get("VLLM_MAX_LEN", "4096"))

hf_secret = modal.Secret.from_name("huggingface", required_keys=["HF_TOKEN"])
model_cache = modal.Volume.from_name("cbt-model-cache", create_if_missing=True)


@app.cls(
    gpu=GPU,
    image=image,
    secrets=[hf_secret],
    scaledown_window=300,
    timeout=900,
    volumes={"/root/.cache/huggingface": model_cache},
)
class CBTvLLMService:
    @modal.enter()
    def load(self):
        """Once per cold start: build the vLLM engine (weights come from the
        shared HF cache volume after the first download)."""
        from huggingface_hub import login
        from vllm import LLM

        if os.environ.get("HF_TOKEN"):
            login(os.environ["HF_TOKEN"])

        t0 = time.time()
        self.llm = LLM(
            model=HF_REPO,
            dtype="bfloat16",
            max_model_len=MAX_MODEL_LEN,
            gpu_memory_utilization=0.90,
            enforce_eager=ENFORCE_EAGER,
        )
        self.tokenizer = self.llm.get_tokenizer()
        print(f"vLLM engine ready ({HF_REPO}, gpu={GPU}, "
              f"eager={ENFORCE_EAGER}) in {time.time() - t0:.1f}s")

    @modal.method()
    def generate(self, messages: list, n_responses: int = 3,
                  temperature: float = 0.8, top_p: float = 0.9,
                  max_new_tokens: int = 400) -> dict:
        from vllm import SamplingParams

        t0 = time.time()
        # Qwen2.5 natively supports the system role — same templating as the
        # transformers service, so outputs stay comparable.
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)

        params = SamplingParams(
            n=max(1, int(n_responses)),
            temperature=float(temperature),
            top_p=float(top_p),
            max_tokens=int(max_new_tokens),
        )
        outs = self.llm.generate([prompt], params)
        responses = [o.text.strip() for o in outs[0].outputs]

        total = time.time() - t0
        return {
            "responses": responses,
            "timing": {
                "total_seconds": total,
                "per_response_seconds": total / max(len(responses), 1),
            },
            "mode": "modal",
            "model": HF_REPO,
        }


# ─────────────────────────────────────────────────────────────────────────────
# HTTP endpoints (same shapes as llm_service.py)
# ─────────────────────────────────────────────────────────────────────────────
@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def generate(body: dict):
    """POST /generate"""
    svc = CBTvLLMService()
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
        "engine": "vllm",
        "gpu": GPU,
        "role": "primary_responder",
    }


@app.local_entrypoint()
def debug():
    """`modal run modal/llm_service_vllm.py` — one smoke generation."""
    svc = CBTvLLMService()
    out = svc.generate.remote(
        messages=[{"role": "system", "content": "You are a CBT assistant."},
                  {"role": "user", "content": "I always fail at everything."}],
        n_responses=2, temperature=0.7, max_new_tokens=120)
    print("timing:", out["timing"])
    for i, r in enumerate(out["responses"]):
        print(f"--- draft {i} ---\n{r[:300]}\n")
