"""
Claude-provider gates — the mandatory re-validation before the demo swap.

Runs LOCALLY through the real backend code (safety_gate.assess /
llm_client.generate) with LLM_PROVIDER=claude, so what's measured is the
exact production path: regex heuristic + Claude triage combined, and the
Claude responder behind the same prompt + choke-point detectors.

    LLM_PROVIDER=claude MOCK_LLM=false python scripts/claude_gate.py --crisis
    LLM_PROVIDER=claude MOCK_LLM=false python scripts/claude_gate.py --heldout
    python scripts/dpo_ab_eval.py --compare v35 claude   # after --heldout

Outputs mirror the existing gate files (crisis_claude.json / ab_claude.json)
so every --compare tool keeps working.
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

# Local runs have no Redis server — fail the breaker OPEN so calls proceed.
from app.services import redis_client as rc          # noqa: E402
rc.circuit_should_call = lambda: True
rc.circuit_record_success = lambda: None
rc.circuit_record_failure = lambda: None

from app.core.config import settings                 # noqa: E402
from dpo_crisis_gate import _crisis_rows             # noqa: E402

OUT_DIR = Path(__file__).parent / "dpo_data"
OUT_DIR.mkdir(exist_ok=True)


def crisis():
    """147 crisis examples through the PRODUCTION gate (regex ∨ Claude)."""
    from app.services import safety_gate
    rows = _crisis_rows()
    print(f"[claude] {len(rows)} crisis examples -> production "
          f"safety_gate.assess (model={settings.claude_model})")
    combined, model_only, heuristic_only = {}, {}, {}
    errors = 0
    for i, (idx, _system, text) in enumerate(rows):
        try:
            out = safety_gate.assess(text)
            combined[str(idx)] = out.get("triage_level", "?")
            model_only[str(idx)] = out.get("model_level", "?")
            heuristic_only[str(idx)] = out.get("heuristic_level", "?")
        except Exception as e:
            errors += 1
            combined[str(idx)] = "ERROR"
            print(f"  [{idx}] failed: {e}")
        if (i + 1) % 25 == 0:
            c = sum(1 for v in combined.values() if v in ("L0", "L1"))
            print(f"  {i+1}/{len(rows)} — combined recall {c}/{len(combined)}",
                  flush=True)
        time.sleep(0.4)          # tier-1 pacing; retries handle 429 anyway
    n = len(rows)
    c = sum(1 for v in combined.values() if v in ("L0", "L1"))
    m = sum(1 for v in model_only.values() if v in ("L0", "L1"))
    h = sum(1 for v in heuristic_only.values() if v in ("L0", "L1"))
    summary = {
        "tag": "claude", "model": settings.claude_model, "n": n,
        "caught": c, "errors": errors,
        "recall": round(c / n, 4),
        "model_only_recall": round(m / n, 4),
        "heuristic_only_recall": round(h / n, 4),
        "levels": combined,
    }
    (OUT_DIR / "crisis_claude.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[claude] PRODUCTION combined recall: {c}/{n} = {c/n:.3f}")
    print(f"[claude] model-only: {m}/{n} = {m/n:.3f} | heuristic-only: "
          f"{h}/{n} = {h/n:.3f} | errors={errors}")


def crisis_sft():
    """The APPLES-TO-APPLES safety test: Claude under the SAME benchmark
    SFT system prompt that gave the fine-tune 96.6% (dpo_crisis_gate
    --path sft). Sends the example's own system prompt, parses risk_level."""
    import re
    from app.services import claude_client
    rows = _crisis_rows()
    print(f"[claude-sft] {len(rows)} crisis examples, SFT-format prompt "
          f"(model={settings.claude_model})")
    levels, errors = {}, 0
    for i, (idx, system, text) in enumerate(rows):
        try:
            out = claude_client.generate(
                [{"role": "system", "content": system},
                 {"role": "user", "content": text}], n=1, max_tokens=200)
            raw = (out.get("responses") or [""])[0]
            m = re.search(r'"?risk_level"?\s*[:=]\s*"?([a-z_]+)', raw, re.I)
            levels[str(idx)] = ("L0" if m and m.group(1).lower() == "crisis"
                                else (m.group(1) if m else "?"))
        except Exception as e:
            errors += 1; levels[str(idx)] = "ERROR"
            print(f"  [{idx}] failed: {e}")
        if (i + 1) % 25 == 0:
            c = sum(1 for v in levels.values() if v in ("L0", "L1"))
            print(f"  {i+1}/{len(rows)} — recall {c}/{len(levels)}", flush=True)
        time.sleep(0.3)
    n = len(rows)
    c = sum(1 for v in levels.values() if v in ("L0", "L1"))
    summary = {"tag": "claude_sft", "model": settings.claude_model, "n": n,
               "caught": c, "recall": round(c / n, 4), "errors": errors,
               "levels": levels}
    (OUT_DIR / "crisis_claude_sft.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[claude-sft] model-only crisis recall (SFT-format): "
          f"{c}/{n} = {c/n:.3f}  [vs v3.5 fine-tune 0.966]")


def heldout(n_drafts: int = 3):
    """38 held-out inputs through llm_client (Claude responder), scored by
    the production detectors — comparable with ab_v*.json."""
    from app.services.prompt_builder import build_messages
    from app.services.post_process import parse_draft
    from app.services import llm_client
    from gen_onpolicy_dpo import _score

    inputs = [l.strip() for l in
              (Path(__file__).parent / "dpo_holdout_inputs.txt")
              .read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.startswith("#")]
    print(f"[claude] {len(inputs)} held-out inputs x {n_drafts} drafts")
    total, clean, fail_counts, lengths = 0, 0, Counter(), []
    for i, text in enumerate(inputs):
        msgs = build_messages(text, intake=None, analysis=None,
                              session_ctx=None, retrieved=[])
        gen = llm_client.generate(msgs, n=n_drafts)
        if gen.get("degraded") or gen.get("mode") != "claude":
            print(f"  [{i}] degraded/mock — skipped"); continue
        for raw in gen.get("responses") or []:
            d = parse_draft(raw)
            s = _score(d["response"], text)
            total += 1
            lengths.append(len(d["response"]))
            if s["fails"] == 0:
                clean += 1
            for w in s["why"]:
                fail_counts[w] += 1
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(inputs)} — clean {clean}/{total}", flush=True)
    summary = {
        "tag": "claude", "workspace": settings.claude_model,
        "inputs": len(inputs), "drafts_scored": total, "clean": clean,
        "clean_rate": round(clean / total, 3) if total else None,
        "failure_counts": dict(fail_counts),
        "failure_rates": {k: round(v / total, 3)
                          for k, v in fail_counts.items()} if total else {},
        "avg_len": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "failed_calls": 0, "n": n_drafts, "temperature": None,
    }
    (OUT_DIR / "ab_claude.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--crisis", action="store_true")
    ap.add_argument("--crisis-sft", action="store_true")
    ap.add_argument("--heldout", action="store_true")
    a = ap.parse_args()
    if a.crisis:
        crisis()
    if a.crisis_sft:
        crisis_sft()
    if a.heldout:
        heldout()
    if not (a.crisis or a.crisis_sft or a.heldout):
        print(__doc__)
