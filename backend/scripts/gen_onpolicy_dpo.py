"""
ON-POLICY DPO pairs — rejected/chosen are the model's OWN drafts, judged by
the same deterministic quality detectors the pipeline already trusts.

Why on-policy: DPO shifts probability away from what the policy actually
produces. Template strawmen teach it to avoid OUR writing; its own failed
drafts teach it to avoid ITS habits — on every input distribution it
actually sees.

Two sources:

  --from-db      Every stored session already holds 3-4 real drafts for a
                 real user message. Score each draft; a clean one becomes
                 `chosen`, each failing sibling becomes `rejected`. $0.

  --probe FILE   One user message per line (see dpo_probe_inputs.txt) →
                 brain /generate (production prompt, no RAG) → n drafts →
                 same scoring. Covers input styles the DB lacks (~$1-2 GPU).
                 Uses MODAL_LLM_ENDPOINT or MODAL_BRAIN_WORKSPACE from env.

Sessions/probes where NO draft is clean go to needs_chosen.jsonl — a human
writes the chosen there (that is the only hand-written part).

Finally --combine merges seed + DB-harvest + onpolicy (+ needs_chosen rows
that got a "chosen" filled in) into dpo_all.jsonl for modal/train_dpo.py.

    DATABASE_URL=<railway-public-url> python scripts/gen_onpolicy_dpo.py --from-db
    python scripts/gen_onpolicy_dpo.py --probe scripts/dpo_probe_inputs.txt
    python scripts/gen_onpolicy_dpo.py --combine
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.chat import (_reask_count, _question_count,      # noqa: E402
                          _DELIVERY_REQ)
from app.services.prompt_builder import (_QUOTED_THOUGHT,     # noqa: E402
                                         _STATED_THOUGHT, build_messages)
from app.services.preflight import _REF_ECHO                  # noqa: E402
from app.services.post_process import parse_draft             # noqa: E402
from app.core.config import settings                          # noqa: E402

OUT_DIR = Path(__file__).parent / "dpo_data"
OUT_DIR.mkdir(exist_ok=True)

TASK = ("[CLINICAL TASK]\nReply as the CBT clinician in the "
        "Technique/Rationale/Plan/Response format.")

# Vocative-name leak: ", Ryan." / "Ryan, thank you" / "Hi Faith," — reuse the
# production scrubber's view of the world: if scrubbing with an empty
# allowlist changes the text, a name leaked.
from app.services.post_process import scrub_unknown_names     # noqa: E402


def _named(text: str) -> bool:
    return bool(_QUOTED_THOUGHT.search(text or "")
                or _STATED_THOUGHT.search(text or ""))


def _score(resp: str, user_text: str) -> dict:
    """Deterministic quality read on one draft. Higher `fails` = worse."""
    resp = (resp or "").strip()
    fails, why = 0, []
    if _named(user_text) and _reask_count(resp) > 0:
        fails += 2; why.append("reask_after_named")
    if _DELIVERY_REQ.search(user_text) and _question_count(resp) > 0:
        fails += 2; why.append("question_on_delivery_ask")
    if _REF_ECHO.search(resp):
        fails += 3; why.append("reference_echo")
    if scrub_unknown_names(resp, allowed=set()) != resp:
        fails += 3; why.append("borrowed_name")
    if re.search(r"\b(again|as we discussed|last time|you filled out|"
                 r"you wrote)\b", resp, re.I):
        fails += 2; why.append("fabricated_continuity")
    if len(resp) < 120:
        fails += 1; why.append("too_thin")
    if resp.endswith("?") and not _DELIVERY_REQ.search(user_text):
        fails += 0  # ending on a question alone isn't a failure
    return {"fails": fails, "why": why}


def _completion(technique: str, rationale: str, plan: str, response: str):
    return (f"Technique: {technique or 'Supportive counselling'}\n"
            f"Rationale: {rationale or ''}\n"
            f"Plan: {plan or ''}\n"
            f"Response: {response}")


def _pairs_from_drafts(prompt: str, user_text: str, drafts: list,
                       source: str, sid: str):
    """drafts: [{technique, rationale, plan, response}] → pairs / needs."""
    scored = []
    for d in drafts:
        if not (d.get("response") or "").strip():
            continue
        scored.append((d, _score(d["response"], user_text)))
    if len(scored) < 2:
        return [], []
    clean = [x for x in scored if x[1]["fails"] == 0
             and len(x[0]["response"]) >= 150]
    dirty = [x for x in scored if x[1]["fails"] >= 2]
    if clean and dirty:
        best = max(clean, key=lambda x: len(x[0]["response"]))[0]
        chosen = _completion(best.get("technique"), best.get("rationale"),
                             best.get("plan"), best["response"])
        return [{
            "prompt": prompt, "chosen": chosen,
            "rejected": _completion(d.get("technique"), d.get("rationale"),
                                    d.get("plan"), d["response"]),
            "source": source, "session_id": sid,
            "reject_why": s["why"],
        } for d, s in dirty], []
    if dirty and not clean:                      # every draft failed → human
        worst = max(dirty, key=lambda x: x[1]["fails"])
        return [], [{
            "prompt": prompt,
            "rejected": _completion(worst[0].get("technique"), "", "",
                                    worst[0]["response"]),
            "source": source + "_needs", "session_id": sid,
            "reject_why": worst[1]["why"],
        }]
    return [], []


# ---------------------------------------------------------------------------
def run_from_db():
    from app.db.session import db_session
    from app.core.crypto import decrypt_str
    from app.db import models
    from harvest_dpo import _thread_prompt

    pairs, needs = [], []
    with db_session() as db:
        sessions = (db.query(models.Session)
                      .filter(models.Session.status.in_(
                          ["answered", "auto_sent", "pending_review"]))
                      .all())
        for sess in sessions:
            drafts = (db.query(models.Draft)
                        .filter_by(session_id=sess.id)
                        .order_by(models.Draft.idx).all())
            if len(drafts) < 2:
                continue
            user_text = decrypt_str(sess.user_input_enc)
            ds = [{"technique": d.technique, "rationale": d.rationale,
                   "plan": d.plan, "response": decrypt_str(d.response_enc)}
                  for d in drafts]
            p, n = _pairs_from_drafts(_thread_prompt(db, sess), user_text,
                                      ds, "db_onpolicy", str(sess.id))
            pairs += p; needs += n
    _write("onpolicy_db_pairs.jsonl", pairs)
    _append("needs_chosen.jsonl", needs)
    print(f"onpolicy_db_pairs.jsonl : {len(pairs)} pairs | "
          f"needs_chosen +{len(needs)}")


def run_probe(path: str, n: int = 4, temp: float = 0.7):
    url = settings.modal_llm_endpoint
    if not url:
        raise SystemExit("no LLM endpoint — set MODAL_BRAIN_WORKSPACE or "
                         "MODAL_LLM_ENDPOINT")
    inputs = [l.strip() for l in Path(path).read_text(encoding="utf-8")
              .splitlines() if l.strip() and not l.startswith("#")]
    print(f"probing {len(inputs)} inputs x {n} drafts against {url}")
    pairs, needs = [], []
    for i, text in enumerate(inputs):
        msgs = build_messages(text, intake=None, analysis=None,
                              session_ctx=None, retrieved=[])
        body = json.dumps({"messages": msgs, "n_responses": n,
                           "temperature": temp}).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                out = json.loads(r.read().decode())
        except Exception as e:
            print(f"  [{i}] FAILED: {e}"); continue
        drafts = [parse_draft(raw) for raw in out.get("responses") or []]
        prompt = f"[CURRENT CLIENT MESSAGE]\n{text}\n{TASK}"
        p, nd = _pairs_from_drafts(prompt, text, drafts,
                                   "probe_onpolicy", f"probe-{i}")
        pairs += p; needs += nd
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(inputs)} done — {len(pairs)} pairs so far")
    fname = f"onpolicy_probe_pairs_t{str(temp).replace('.', '')}.jsonl"
    _write(fname, pairs)
    _append("needs_chosen.jsonl", needs)
    print(f"{fname} : {len(pairs)} pairs | needs_chosen +{len(needs)}")


def run_combine():
    files = (["seed_transcript_pairs.jsonl", "pairs.jsonl",
              "onpolicy_db_pairs.jsonl"]
             + sorted(p.name for p in OUT_DIR.glob("onpolicy_probe_pairs*.jsonl"))
             + ["needs_chosen_filled.jsonl"])
    all_rows, seen = [], set()
    for name in files:
        p = OUT_DIR / name
        if not p.exists():
            print(f"  (skip {name})"); continue
        cnt = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "chosen" not in row or "rejected" not in row:
                continue
            key = (row["prompt"][:150], row["rejected"][:150])
            if key in seen:
                continue
            seen.add(key); all_rows.append(row); cnt += 1
        print(f"  + {name}: {cnt}")
    _write("dpo_all.jsonl", all_rows)
    print(f"dpo_all.jsonl : {len(all_rows)} pairs -> modal/train_dpo.py")


def _write(name, rows):
    with open(OUT_DIR / name, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _append(name, rows):
    with open(OUT_DIR / name, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-db", action="store_true")
    ap.add_argument("--probe", default="")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--combine", action="store_true")
    a = ap.parse_args()
    if a.from_db:
        run_from_db()
    if a.probe:
        run_probe(a.probe, a.n, a.temp)
    if a.combine:
        run_combine()
    if not (a.from_db or a.probe or a.combine):
        print(__doc__)
