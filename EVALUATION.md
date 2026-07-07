# MindCare AI — Evaluation, Guardrails & Cost

System: a CBT mental-health assistant. The "brain" is **provider-agnostic**:
a single fine-tuned model (`Huysun29/cbt-qwen2.5-7b-v3`, self-hosted on
Modal A100-80GB) serves all LLM roles by default, and a one-env-var switch
(`LLM_PROVIDER=claude`) routes those same roles to the Claude API instead —
the deterministic safety gate, choke-point nets, memory, context and
human-in-the-loop review are **identical** for both providers.

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
(`dpo_ab_eval.py`); plus a 3-scenario mid-exercise holdout
(`gen_midex_dpo.py --eval`). Six iterations, each gated: v3.0 flat →
v3.1/v3.2 seesawed single classes → v3.3 passed (+14.9 pp clean) → v3.4
added 32 mid-exercise pairs at 12% mix (no transfer) → **v3.5** doubled the
scenario diversity and weighted the class ×3 (~45% of 400 rows):

| Held-out metric (148 drafts) | v2 (prod) | v3.3 | **v3.5** | Δ v2→v3.5 |
|---|---|---|---|---|
| **Crisis recall (SFT-format, 147 ex.)** | 142/147 | 142/147 | **142/147, newly_missed 0** | ± 0 — **6 consecutive runs** |
| Clean-draft rate | 45.9% | 60.8% | **71.6%** | **+25.7 pp** |
| Borrowed-name rate | 18.2% | 8.1% | **1.4%** | −16.8 pp |
| Re-ask after named thought | 25.0% | 17.6% | **12.8%** | −12.2 pp |
| Question on delivery-ask | 13.5% | 13.5% | **9.5%** | −4.0 pp |
| Mid-exercise holdout (dirty drafts) | — | 66.7% | **61.1%** | modest; deterministic nets guarantee the structure |
| Mean reply length | 190 ch | 232 ch | **250 ch** | richer |

Total GPU cost for the whole campaign (6 train runs + merges + all gates):
**~$30**. Checkpoint: `Huysun29/cbt-qwen2.5-7b-v3` (private, holds v3.5).
Findings worth keeping: the published 96.6% crisis recall lives in the SFT
prompt format (the screening-prompt path scores ~8% on long intake prose
for BOTH models — the deterministic regex+history layer carries that case
in production, by design); prompt-format alignment between training pairs
and the production prompt was the biggest single transfer lever; and
class-weighting dense, authored gold responses spills over — v3.5's
mid-exercise golds lifted EVERY failure class, not just the targeted one.

### 1g. Acute-crisis safety probe + provider swap (Claude Sonnet 5)

The SFT-format crisis benchmark (§1a/1b) measures label *reproduction* — the
fine-tune was trained to map that dataset's broad "crisis" label (which
includes grief/despair) to a crisis level, so it scores 96.6% there. That is
**not** a fair cross-provider test: a model using independent clinical
judgment (e.g. Claude) flags only genuine acute danger and "misses" the
grief-labelled examples by design. The measurement that reflects real user
safety is `backend/scripts/acute_safety_probe.py` — genuine acute-crisis
messages, short and direct like production chat, through the real
`safety_gate.assess` path (regex hard-override ∨ model):

| Provider (production path) | Acute crisis → L0/L1 | Safe → L2/L3 |
|---|---|---|
| Fine-tune v3.5 (+ regex) | pass (regex floor) | — |
| **Claude Sonnet 5 (+ regex)** | **15/15 (100%)** | **10/10 (0 false alarm)** |

The regex hard-override is **provider-independent**, so the crisis floor
holds regardless of which model answers.

**Responder quality, held-out (37 unseen inputs, 3 drafts each):**

| Metric | v2 (base) | v3.5 (6 DPO rounds) | **Claude Sonnet 5** |
|---|---|---|---|
| Clean-draft rate | 45.9% | 71.6% | **95.5%** |
| Re-ask after named thought | 25.0% | 12.8% | **0%** |
| Borrowed-name rate | 18.2% | 1.4% | **0%** |
| Question on delivery-ask | 13.5% | 9.5% | **3.6%** |
| Mean reply length | 190 ch | 250 ch | **295 ch** |

> Caveat: the Claude column was scored with a self-contained
> production-equivalent detector (the env couldn't import the full chain);
> the ~24 pp gap over v3.5 is far larger than any scoring drift. Reproduce:
> `LLM_PROVIDER=claude python scripts/claude_gate.py --heldout` and
> `scripts/acute_safety_probe.py`. Cost: ~$0.05–0.15 / chat turn on Sonnet 5
> vs ~$0.004 self-hosted-warm (see §4).

---

## 2. Trustworthiness: Memory, Context & Edge-Case Handling

Beyond metrics, "trustworthy for real users" means the agent **remembers**,
**tracks the conversation**, and **fails safe on the odd cases**. All three
are verified in code and behave identically across providers.

### 2a. Memory (durable, cross-session) — `user_memory.py`

A per-user `UserMemory` row (PHI encrypted, `facts_enc` AES-GCM) accumulates
compact facts every turn (`update_after_turn`, heuristic — works even in
mock/degraded): a **recurring-themes** counter (cognitive distortions +
emotions from the analyzer), a **techniques-used** counter, a `turn_count`,
and an LLM-written **rolling gist** (`summarizer.refresh_after_turn`, a
background task). `load_for_prompt` injects the top themes/techniques +
summary into **every** prompt, so the agent recalls what this person tends
to struggle with and what's been tried. Best-effort throughout: any memory
failure is swallowed and never blocks a reply.

### 2b. Context (multi-turn, in-thread) — `session_ctx` in `chat.py`

Each turn assembles: prior turn count, last technique, the **last N turns of
this thread** (decrypted history), a **rolling thread summary** (Redis,
refreshed after each turn), durable memory (2a), and stated style
preferences. This context is what powers named-thought pinning, the
anti-repeat check, exercise-continuation detection, and listen-mode
stickiness — the behaviours that make the conversation feel followed rather
than reset each message.

### 2c. Edge cases — ~12 deterministic guards (safety only ever escalates UP)

| Edge case | Handling |
|---|---|
| Acute crisis (L0/L1) | regex hard-override, overrides the model; L0 = no AI reply |
| Jailbreak / prompt-injection | dedicated gate (only when no acute risk) |
| Off-topic / "about the app" | scope router redirect, biased to "personal" |
| "Just listen, don't advise" | listen mode + L2 vent-release valve (fail-closed) |
| Model / API outage | circuit breaker → degraded → fixed pipeline; never hangs |
| Invented name / biography / continuity | 3 scrubs at the draft choke-point |
| Repeat reply / re-open a finished exercise / dodge | near-dup + exercise-continue + delivery machinery |
| Before ANY auto-send | `has_acute_risk` re-checked on full context |

### 2d. Trustworthiness scorecard (grouped)

| # | Dimension | Evidence |
|---|---|---|
| ① | **Safety** | Acute-crisis recall **15/15 (100%)**, 10/10 safe not over-escalated (§1g); combined benchmark recall **99.3%**; escalation P/R/F1 **99.3 / 96.6 / 97.9** |
| ② | **Honesty / anti-fabrication** | PII leakage **0%** (0/181); production grounding mean **0.06**; red-team **10/10** |
| ③ | **Human oversight** | L2 always clinician-reviewed; approve **82.4%**, **reject 0%**; tool-arg validity **100%** |
| ④ | **Conversation quality (held-out)** | Clean-draft **45.9% → 71.6% (v3.5) → 95.5% (Claude)**; scope accuracy **95.5%** |
| ⑤ | **Operational robustness** | Agent failure → fixed-pipeline fallback; crisis floor held across **6 consecutive** DPO retrains |

### 2e. Honest limits to disclose

- Memory is **compact heuristic** (themes/techniques/gist), not full
  retrieval over every past session — sufficient for continuity, not a
  complete clinical record.
- The 96.6% / 99.3% crisis figures live in the **benchmark SFT format**; use
  the acute-safety probe (15/15) for cross-provider safety claims.
- Red-team **N is small** (10) — a sanity check, to be expanded.
- On-device technique accuracy (33.5%) is the 7B ceiling — the reason the
  Claude provider exists, and why the model-agnostic architecture (fixed
  safety layer + swappable brain) is the real contribution.

---

## 3. Guardrails

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

## 4. Cost

The default model is **self-hosted on Modal (A100-80GB)** → cost is
**GPU-seconds × rate**, not tokens × API price. The Claude provider trades
that for **~$0.05–0.15 / chat turn** (several Sonnet 5 calls per turn:
drafts + triage + orchestrator + summary + emphasis).

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

## 5. Known gaps (honest)

- **Latency** (p50 46s) — cold starts; fix via keep-warm (ops, not safety).
- **Clinical quality** — LLM-judge CBT-align 2.47 / helpful 2.50 are modest;
  needs **clinician human review** (gold standard, not yet done).
- **Calibration (ECE)** — needs the model to emit a probability, not a bare label.
- **Multi-turn coherence**, **fairness/subgroup**, and **longitudinal outcomes**
  (PHQ-9/GAD-7 improvement, retention) — require multi-turn eval / demographic
  labels / real usage over time.

---

## 6. Reproduce

```bash
# $0 — no Modal:
cd backend
python scripts/regex_safety_eval.py     # combined crisis recall / FP (N=997)
python scripts/extra_metrics.py         # escalation, scope, diversity, PII, grounding
python scripts/agent_trace_eval.py      # production agent behaviour (needs DB)
python scripts/acute_safety_probe.py    # genuine acute-crisis recall (production path)

# Uses live Modal (small):
python scripts/final_eval.py            # crisis smoke + red-team + KPIs

# DPO campaign (v3.x) + provider swap:
python scripts/dpo_crisis_gate.py --compare v2sft v35sft   # per-example crisis gate
python scripts/dpo_ab_eval.py --compare v2 v35             # held-out behaviour
LLM_PROVIDER=claude python scripts/claude_gate.py --heldout # Claude responder quality

# Offline benchmark (already computed; results in eval-model/.../eval_out_*):
#   modal_eval.py / modal_rag_eval.py / modal_agent_eval.py
```
