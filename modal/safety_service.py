"""
Modal Safety Gate service — Huysun29/cbt-qwen-7b
(QWen2.5-7B Instruct + CBT safety LoRA adapter)

Role: safety/crisis gate — router and guard for the CBT pipeline.
      Classifies every client message before the main LLM responds.

Endpoints used by backend/app/services/safety_gate.py:
    POST /assess   { messages } → { level, severity, reason, confidence }
    GET  /health   → { status, model, gpu }

Deploy:
    modal deploy modal/safety_service.py

After deploy, add to your .env:
    MODAL_SAFETY_ENDPOINT=https://<workspace>--cbt-safety-assess.modal.run
    MODAL_SAFETY_HEALTH_ENDPOINT=https://<workspace>--cbt-safety-health.modal.run

Notes
-----
- QWen2.5-7B uses a standard chat template with a system role.
- T4 (16 GB) is sufficient for 7B bf16 inference.
- temperature=0.05 keeps triage nearly deterministic.
- The model outputs JSON in the format:
    {"level":"L0|L1|L2|L3","severity":"...","reason":"...","confidence":0.0}
"""
import os
import json
import re
import time

import modal

# ─────────────────────────────────────────────────────────────────────────────
# Container image
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
    )
)

app = modal.App("cbt-safety")

HF_REPO = os.environ.get("HF_SAFETY_MODEL_REPO", "Huysun29/cbt-qwen-7b")
HF_BASE = os.environ.get("HF_SAFETY_BASE_MODEL", "Qwen/Qwen2.5-7B-Instruct")

hf_secret = modal.Secret.from_name("hf-secret", required_keys=["HF_TOKEN"])

SYSTEM_PROMPT = (
    "You are a mental health safety triage system trained as a clinical CBT "
    "specialist. Your ONLY task is to classify the client message into exactly "
    "one safety level and return structured JSON.\n\n"
    "Safety levels:\n"
    "  L0 CRISIS   — active suicidal or homicidal ideation, immediate danger\n"
    "  L1 HIGH     — passive ideation or significant self-harm risk\n"
    "  L2 MODERATE — clinical distress (depression/anxiety/ptsd) without "
    "imminent danger\n"
    "  L3 ROUTINE  — general mental-health concern, standard CBT response\n\n"
    "Respond ONLY with valid JSON (no markdown, no explanation):\n"
    '{"level":"<L0|L1|L2|L3>","severity":"<critical|high|moderate|low>",'
    '"reason":"<one sentence>","confidence":<0.0-1.0>}'
)


# ─────────────────────────────────────────────────────────────────────────────
# Modal class
# ─────────────────────────────────────────────────────────────────────────────
@app.cls(
    gpu="T4",                      # 16 GB VRAM — sufficient for QWen-7B bf16
    image=image,
    secrets=[hf_secret],
    container_idle_timeout=300,
    timeout=120,
)
class CBTSafetyService:
    @modal.enter()
    def load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        from huggingface_hub import login

        login(os.environ["HF_TOKEN"])

        print(f"Loading safety base model: {HF_BASE}")
        self.tokenizer = AutoTokenizer.from_pretrained(HF_BASE)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        base = AutoModelForCausalLM.from_pretrained(
            HF_BASE,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        print(f"Attaching safety LoRA: {HF_REPO}")
        self.model = PeftModel.from_pretrained(base, HF_REPO)
        self.model.eval()
        print("CBT QWen-7B safety gate ready.")

    @modal.method()
    def assess(self, messages: list) -> dict:
        import torch
        t0 = time.time()

        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)

        inputs = self.tokenizer(
            prompt, return_tensors="pt",
            truncation=True, max_length=1024,
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=120,
                do_sample=True,
                temperature=0.05,
                top_p=0.9,
                num_return_sequences=1,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        prompt_len = inputs["input_ids"].shape[1]
        raw = self.tokenizer.decode(
            outputs[0][prompt_len:], skip_special_tokens=True).strip()

        # Parse JSON from model output
        m = re.search(r'\{[^{}]*"level"\s*:\s*"L[0-3]"[^{}]*\}', raw, re.S)
        if m:
            try:
                result = json.loads(m.group())
                return {
                    "level": result.get("level", "L3"),
                    "severity": result.get("severity", "low"),
                    "reason": result.get("reason", ""),
                    "confidence": float(result.get("confidence", 0.7)),
                    "latency_ms": round((time.time() - t0) * 1000),
                    "mode": "modal",
                    "model": HF_REPO,
                }
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: scan for level keyword
        for lv in ("L0", "L1", "L2", "L3"):
            if lv in raw:
                return {"level": lv, "severity": _lv_to_sev(lv),
                        "reason": "parsed from model output",
                        "confidence": 0.6, "mode": "modal_fallback"}

        return {"level": "L3", "severity": "low",
                "reason": "model output unparseable — defaulting to L3",
                "confidence": 0.3, "mode": "modal_fallback"}


def _lv_to_sev(lv: str) -> str:
    return {"L0": "critical", "L1": "high", "L2": "moderate"}.get(lv, "low")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def assess(body: dict):
    """POST /assess  — safety triage for a client message"""
    svc = CBTSafetyService()
    return svc.assess.remote(messages=body.get("messages", []))


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def health():
    """GET /health"""
    return {
        "status": "ok",
        "model": HF_REPO,
        "base": HF_BASE,
        "role": "safety_crisis_gate",
    }
