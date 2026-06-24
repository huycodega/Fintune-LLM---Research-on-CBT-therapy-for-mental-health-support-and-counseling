"""
Agent PRODUCTION-trace eval — READ-ONLY, no Modal needed.

Complements scripts/agent_eval.py (which runs a labelled suite through the LIVE
orchestrator). This one mines what the agent ALREADY recorded on real sessions
(Session.analysis["agent_trace"] / self-critique / rag_gate + Draft.
hallucination_score) and prints how the agent is behaving in production. It
performs NO writes and is never imported by the running app, so it cannot
affect the live agent.

Run (from backend/, pointed at the same DATABASE_URL as prod or via railway run):
    python scripts/agent_trace_eval.py
    python scripts/agent_trace_eval.py --days 30

Read the headlines:
  • forced_generate %   high → orchestrator (Modal) unreliable / timing out
  • malformed-args %    high → model emits bad tool calls
  • prose %             high → model replies in prose instead of calling tools
  • near-zero grounding → fabrication risk (these were held for review)
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _pct(n, d):
    return f"{(100.0 * n / d):.1f}%" if d else "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="only sessions newer than N days (0 = all)")
    args = ap.parse_args()

    from app.db.session import db_session
    from app.db import models

    with db_session() as db:
        q = db.query(models.Session)
        if args.days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
            q = q.filter(models.Session.created_at >= cutoff)
        sessions = q.all()
        agent_sessions = [s for s in sessions
                          if isinstance(s.analysis, dict) and s.analysis.get("agent_trace")]
        ground = [d.hallucination_score for d in db.query(models.Draft).all()
                  if d.hallucination_score is not None]

    total = len(agent_sessions)
    print("=" * 64)
    print(" AGENT PRODUCTION-TRACE EVAL  (read-only)")
    print(f" sessions scanned: {len(sessions)}   |   agent ran on: {total}"
          + (f"   |   last {args.days}d" if args.days else ""))
    print("=" * 64)
    if total == 0:
        print(" No agent traces found (agent disabled, or pipeline fallback in use).")
        return

    tool_calls, bad_args, terminals, outcome = Counter(), Counter(), Counter(), Counter()
    steps_per = []
    prose_sessions = forced_sessions = unknown_tool = 0
    grounded_generate = total_generate = 0
    self_critique_sessions = self_critique_applied = 0

    for s in agent_sessions:
        trace = s.analysis.get("agent_trace") or []
        steps = {t.get("step") for t in trace if isinstance(t, dict) and t.get("step") is not None}
        steps_per.append(len(steps) or len(trace))
        had_prose = had_forced = False
        for t in trace:
            if not isinstance(t, dict):
                continue
            tool = t.get("tool", "")
            if tool == "_prose":
                had_prose = True; continue
            if tool == "_forced_generate":
                had_forced = True; continue
            if tool.startswith("_"):
                continue
            tool_calls[tool] += 1
            if t.get("missing_args"):
                bad_args[tool] += 1
            if "Unknown tool" in str(t.get("result", "")):
                unknown_tool += 1
            if tool in ("generate_cbt_response", "ask_clarification", "escalate_to_clinician"):
                terminals[tool] += 1
            if tool == "generate_cbt_response":
                total_generate += 1
                if t.get("model_grounded"):
                    grounded_generate += 1
        prose_sessions += had_prose
        forced_sessions += had_forced
        self_critique_sessions += bool(s.analysis.get("agent_self_critique"))
        self_critique_applied += bool(s.analysis.get("agent_self_critique_applied"))
        outcome[s.status or "?"] += 1

    total_tool_calls = sum(tool_calls.values())
    total_bad = sum(bad_args.values())

    print("\n OUTCOME (session status):")
    for k, v in outcome.most_common():
        print(f"   {k:<16} {v:>4}  ({_pct(v, total)})")
    print(f"   forced-generate: {forced_sessions} ({_pct(forced_sessions, total)})"
          "   <- high = orchestrator unreliable")

    print("\n TERMINAL ACTION:")
    for k, v in terminals.most_common():
        print(f"   {k:<24} {v:>4}  ({_pct(v, total)})")

    print("\n TOOL USAGE (calls   bad-args):")
    for k, v in tool_calls.most_common():
        print(f"   {k:<24} {v:>4}   {bad_args.get(k, 0)} ({_pct(bad_args.get(k, 0), v)})")

    print("\n TOOL-CALL QUALITY:")
    print(f"   total tool calls         {total_tool_calls}")
    print(f"   malformed (missing args) {total_bad} ({_pct(total_bad, total_tool_calls)})")
    print(f"   prose-instead-of-tool    {prose_sessions} sessions ({_pct(prose_sessions, total)})")
    print(f"   unknown-tool calls       {unknown_tool}")
    if steps_per:
        print(f"   avg steps / session      {statistics.mean(steps_per):.1f}")

    print("\n GROUNDING (Draft.hallucination_score, higher = better):")
    if ground:
        ground.sort()
        p = lambda qq: ground[min(len(ground) - 1, int(qq * len(ground)))]
        near_zero = sum(1 for g in ground if g < 0.1)
        print(f"   drafts {len(ground)}   mean {statistics.mean(ground):.2f}"
              f"   p10 {p(0.10):.2f}  p50 {p(0.50):.2f}  p90 {p(0.90):.2f}")
        print(f"   near-zero (<0.10, fabrication risk): {near_zero} ({_pct(near_zero, len(ground))})")
    else:
        print("   (no grounding scores recorded)")
    print(f"   generate w/ retrieved context: {grounded_generate}/{total_generate} "
          f"({_pct(grounded_generate, total_generate)})")

    print("\n SELF-CRITIQUE:")
    print(f"   flagged: {self_critique_sessions} ({_pct(self_critique_sessions, total)})"
          f"   applied: {self_critique_applied}")
    print("=" * 64)


if __name__ == "__main__":
    main()
