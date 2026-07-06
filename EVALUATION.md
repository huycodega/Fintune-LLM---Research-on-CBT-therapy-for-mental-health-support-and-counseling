# MindCare AI — Evaluation, Guardrails & Cost

System: a CBT mental-health assistant. A single fine-tuned model
(`Huysun29/cbt-qwen2.5-7b-v2`) serves all roles (safety triage, responder,
agent orchestrator) on Modal (A100-80GB); a deterministic safety gate +
human-in-the-loop clinician review sit around it.

All numbers below are **measured**, not estimated. Reproduce with the scripts in
`backend/scripts/` and `eval-model/`.

---

## 1. Evaluation Metrics (with baselines)

### 1a. Offline benchmark — staged, with model baselines
Test set: `eval-model/.../cbt_test.jsonl` (3,467 examples; M4 subset N=998, 147
crisis). Four candidate models compared (qwen2.5-7b / llama3.1-8b / mistral-7b /
gemma2-9b) across four stages — this **is** the baseline comparison:

| Stage | What | Folder |
|---|---|---|
| M1 | base model | `eval_model_base` |
| M2 | + fine-tune | `eval_model_finetune` |
| M3 | + RAG (bge-m3 + reranker + Qdrant, gated) | `eval_model_finetune_rag` |
| M4 | + agent (ReAct: multi-hop retrieval + self-reflection) | `eval_model_finetune_rag_agent` |

**Winner (M4, qwen2.5-7b):**

| Group | Metric | Value |
|---|---|---|
| Risk | accuracy / macro-F1 | 97.1% / 97.9% |
| Risk | crisis recall (model alone) | 96.6% |
| Safety | unsafe / diagnosis / medication violation | 0.6% / 0.1% / 0.0% |
| Technique | accuracy | 33.5% |
| Quality (LLM-judge 1–5) | empathy / boundary / clarity / tone | 4.14 / 4.98 / 4.68 / 4.25 |
| Quality (LLM-judge 1–5) | CBT-align / tech-correct / helpful / overall | 2.47 / 1.82 / 2.50 / 3.55 |
| RAGAS | faithfulness / answer-rel / context-prec | 0.04 / 0.29 / 0.79 |
| Agent | mean hops / rewrite / reflect / revise | 1.52 / 66% / 19% / 3% |

### 1b. Combined-system safety (deployed gate = regex ∨ model), N=997
`backend/scripts/regex_safety_eval.py` ($0 — reuses M4 preds + live regex):

| Layer | Crisis recall (L0+L1) | False-positive (L2/L3→L0/L1) |
|---|---|---|
| Regex only | 12.2% | 3.6% |
| Model only | 96.6% | 0.1% |
| **Combined (deployed)** | **99.3%** (146/147) | 3.8% |

> The combined gate reaches **99.3% crisis recall** on N=147 — only 1 crisis
> fully missed. The regex layer adds ~3.7% false-positives (over-triage) and can
> cap a true-L0 at L1 (still safe: no AI auto-reply). Note the benchmark input is
> long intake prose; production chat messages are short/direct where the regex
> backstop catches substantially more.

### 1c. Extra trust metrics ($0)
`backend/scripts/extra_metrics.py`:

| Metric | Value |
|---|---|
| Escalation precision / recall / F1 | 99.3% / 96.6% / 97.9% |
| Scope-router accuracy (personal/meta/off-topic) | 95.5% (21/22) |
| Draft diversity (lexical, 50 sessions) | 0.78 |
| **PII leakage in responses** | **0%** (0/181) |
| Production grounding (Draft.hallucination_score) | mean 0.06 (empathic replies → few factual claims) |
| Calibration (ECE) | N/A — model emits a bare risk label, no probability |

### 1d. Red-team ($0)
`backend/scripts/final_eval.py` — adversarial inputs (jailbreak, prompt
injection, self-harm method requests, harmful off-topic): **10/10 handled
safely** (caught or redirected; none complied). Small N — a sanity check, to be
expanded.

### 1e. Production KPIs (real DB)
`backend/scripts/final_eval.py` / `agent_trace_eval.py`:

| KPI | Value |
|---|---|
| Clinician decisions | approve 82.4% · edit 17.6% · reject 0% |
| Agent uptime on L2/L3 | 88.7% (47/53) |
| Tool-arg validity | 100% (0 malformed) |
| Orchestrator reliability | prose 46.8% · forced-generate 42.6% (degrades gracefully) |

### 1f. DPO fine-tune v3.3 — gate-driven behaviour repair (2026-07-05/06)

Production testing exposed six recurring habit failures the runtime guards
were patching per-turn (re-asking after the client already named their
thought, dodging explicit "just tell me" requests, borrowing client names
from nowhere, fabricated continuity, reference echo, thin advice). DPO on
the model's OWN outputs targets the habits at the weights.

**Data (on-policy, no template strawmen):** 148 preference pairs — the
model's real drafts for real/probe inputs, auto-labelled by the production
quality detectors (`gen_onpolicy_dpo.py`); 22 hand-written `chosen` only
where every sampled draft failed. Weighted to 232 rows (re-ask/delivery
pairs ×2, `dpo_all_v33.jsonl`). QLoRA-DPO on H100 (β=0.05, lr 1e-5, 3
epochs, ~75s/run) — `modal/train_dpo.py`.

**Two-part gate, every candidate:** (1) *safety* — the 147-example crisis
set, per-example: `newly_missed == 0` required (`dpo_crisis_gate.py`);
(2) *generalization* — 38 HELD-OUT inputs (new topics AND phrasings, frozen
before training, never trained on) scored by the same detectors
(`dpo_ab_eval.py`). The gate rejected two checkpoints (v3.0 flat, v3.1/v3.2
seesawed single classes) before v3.3 passed:

| Held-out metric (148 drafts) | v2 (prod) | v3.3 | Δ |
|---|---|---|---|
| **Crisis recall (SFT-format, 147 ex.)** | 142/147 | **142/147, newly_missed 0** | ± 0 — 4 consecutive runs |
| Clean-draft rate | 45.9% | **60.8%** | **+14.9 pp** |
| Borrowed-name rate | 18.2% | **8.1%** | −10.1 pp |
| Re-ask after named thought | 25.0% | **17.6%** | −7.4 pp |
| Question on delivery-ask | 13.5% | 13.5% | ± 0 (runtime rewrite covers) |
| Thin-advice rate | 3.4% | 1.4% | −2.0 pp |
| Mean reply length | 190 ch | 232 ch | richer |

Total GPU cost for the whole campaign (4 train runs + merges + all gates):
**~$24**. Checkpoint: `Huysun29/cbt-qwen2.5-7b-v3` (private). Findings worth
keeping: the published 96.6% crisis recall lives in the SFT prompt format
(the screening-prompt path scores ~8% on long intake prose for BOTH models —
the deterministic regex+history layer carries that case in production, by
design); and prompt-format alignment between training pairs and the
production prompt was the single biggest lever for transfer.

---

## 2. Guardrails

| Guardrail | Mechanism | Measured effect |
|---|---|---|
| **Hard crisis gate** | deterministic regex L0/L1 override; **L0 = no AI**, crisis resources shown | combined crisis recall **99.3%** |
| **Human-in-the-loop** | L0/L1/L2 routed to a clinician; AI never auto-replies on sensitive cases | approve 82% / **reject 0%** |
| **Anti-fabrication** | preflight + grounding floor → hold for review; never auto-send a failed/ungrounded draft | gate logic |
| **Agent defense-in-depth** | `has_acute_risk` re-check before any auto-generate; agent may only escalate **UP**, never lower risk | escalation F1 **97.9%** |
| **Scope guardrail** | off-topic / "about-MindCare" redirected (only on safe L3; biased to "personal") | accuracy **95.5%**, red-team **100%** |
| **PII protection** | scrub before any LLM/agent call; PHI encrypted at rest | leakage **0%** |
| **Graceful fallback** | agent failure → fixed pipeline; never blocks a response | architecture |
| **Memory guard** | durable user-memory present → hold for review (prevents memory-narrated fabrication) | gate logic |
| **Audit trail** | every triage/decision/override logged | `audit_trail`, `triage_log` |

---

## 3. Cost

The model is **self-hosted on Modal (A100-80GB)** → cost is **GPU-seconds ×
rate**, not tokens × API price.

**Measured:** M4 generation used `gen_seconds = 3269.4` over N=998 →
**~3.28 GPU-seconds / interaction (warm, batched)**.

Assuming A100-80GB ≈ **$0.0011/sec** (~$3.96/hr — *plug your billed rate*):

| Item | Cost |
|---|---|
| **Warm cost / interaction** | **~$0.0036** (≈ 0.36 cents) |
| Cold-start (one-off, ~120s GPU to load 7B) | ~$0.13 |
| Latency — generation p50 / p95 | **46s / ~16 min** (cold-start tail) |

**API-equivalent** (if a frontier API were used instead of self-hosting,
~5,394 tokens/interaction):

| Alternative | Cost / interaction |
|---|---|
| GPT-4o | ~$0.020 |
| GPT-4o-mini | ~$0.0012 |

> **Takeaway:** warm self-hosted (~$0.004) sits between mini and 4o on cost, but
> **cold starts dominate** both cost (~$0.13 each) and latency (p50 46s) under
> scale-to-zero. The single highest-leverage operational fix is **keeping one
> Modal container warm** (min-containers) — it removes the cold-start cost/latency
> without touching agent logic or safety.

---

## 4. Known gaps (honest)

- **Latency** (p50 46s) — cold starts; fix via keep-warm (ops, not safety).
- **Clinical quality** — LLM-judge CBT-align 2.47 / helpful 2.50 are modest;
  needs **clinician human review** (gold standard, not yet done).
- **Calibration (ECE)** — needs the model to emit a probability, not a bare label.
- **Multi-turn coherence**, **fairness/subgroup**, and **longitudinal outcomes**
  (PHQ-9/GAD-7 improvement, retention) — require multi-turn eval / demographic
  labels / real usage over time.

---

## 5. Reproduce

```bash
# $0 — no Modal:
cd backend
python scripts/regex_safety_eval.py     # combined crisis recall / FP (N=997)
python scripts/extra_metrics.py         # escalation, scope, diversity, PII, grounding
python scripts/agent_trace_eval.py      # production agent behaviour (needs DB)

# Uses live Modal (small):
python scripts/final_eval.py            # crisis smoke + red-team + KPIs

# Offline benchmark (already computed; results in eval-model/.../eval_out_*):
#   modal_eval.py / modal_rag_eval.py / modal_agent_eval.py
```
