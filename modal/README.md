# Modal services — deployment

Two services power the CBT pipeline in production:

| Service | File | Model | Role |
|---------|------|-------|------|
| Primary LLM | `llm_service.py` | `Huysun29/cbt-llama-3.1-8b` | Primary CBT responder |
| Safety Gate | `safety_service.py` | `Huysun29/cbt-qwen-7b` | Crisis / triage router |

## 1. Install Modal CLI (one-time)

```bash
pip install modal
modal token new     # opens browser to link your Modal account
```

## 2. HuggingFace token secret

Both base models (`meta-llama/Meta-Llama-3.1-8B-Instruct` and
`Qwen/Qwen2.5-7B-Instruct`) require accepting their licenses on HF first.

```bash
modal secret create hf-secret HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxx
```

## 3. Deploy both services

```bash
modal deploy modal/llm_service.py      # primary CBT LLM
modal deploy modal/safety_service.py   # safety gate
```

Each deploy prints two HTTPS URLs. Add all four to your `.env`:

```
MOCK_LLM=false

# Primary CBT LLM — Llama-3.1-8B + LoRA
MODAL_LLM_ENDPOINT=https://<workspace>--cbt-llm-generate.modal.run
MODAL_HEALTH_ENDPOINT=https://<workspace>--cbt-llm-health.modal.run

# Safety gate — QWen-7B + LoRA
MODAL_SAFETY_ENDPOINT=https://<workspace>--cbt-safety-assess.modal.run
MODAL_SAFETY_HEALTH_ENDPOINT=https://<workspace>--cbt-safety-health.modal.run
```

Then restart the backend:

```bash
docker compose restart backend
```

## 4. Verify

```bash
# Health checks
curl $MODAL_HEALTH_ENDPOINT
# → {"status":"ok","model":"Huysun29/cbt-llama-3.1-8b","role":"primary_responder"}

curl $MODAL_SAFETY_HEALTH_ENDPOINT
# → {"status":"ok","model":"Huysun29/cbt-qwen-7b","role":"safety_crisis_gate"}

# Test safety triage
curl -X POST $MODAL_SAFETY_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"system","content":"You are a safety triage system..."},{"role":"user","content":"[CLIENT MESSAGE]\nI feel anxious about work"}]}'
# → {"level":"L3","severity":"low","reason":"...","confidence":0.85}

# Test primary LLM
curl -X POST $MODAL_LLM_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"system","content":"You are a CBT clinician..."},{"role":"user","content":"I feel anxious"}],"n_responses":1}'
```

## Cost notes

| Service | GPU | Cost/hr | Cold start | Request latency |
|---------|-----|---------|------------|-----------------|
| LLM (`cbt-llama-3.1-8b`) | A10G | ~$1.10 | ~25-35 s | ~6-10 s (n=3) |
| Safety gate (`cbt-qwen-7b`) | T4 | ~$0.35 | ~15-20 s | ~1-2 s |

`container_idle_timeout=300` (5 min) — both containers scale to zero
between sessions so demo traffic costs cents.

## Architecture

```
Client message
      │
      ▼
[Safety Gate — cbt-qwen-7b]   ← fast, T4, classifies L0/L1/L2/L3
      │
  L0/L1 ──► No AI, crisis resources / clinician queue
      │
  L2/L3 ──► [Primary LLM — cbt-llama-3.1-8b]  ← CBT response
                    │
                    ▼
              Hybrid RAG (cbt_rag_final, BM25 + dense + RRF)
```
