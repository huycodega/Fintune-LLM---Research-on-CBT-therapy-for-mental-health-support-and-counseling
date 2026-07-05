"""
Harvest DPO preference pairs from production clinician decisions.

Closes the data loop: clinician approve/edit decisions in the DB become
(chosen, rejected) pairs for fine-tune v3. Three sources:

  1. APPROVE  — the approved draft is `chosen`; every sibling draft of the
                same session is a `rejected`.
  2. EDIT     — the clinician's edited text is `chosen`; each original draft
                is a `rejected` (the edit IS the correction signal).
  3. LOOP     — auto-sent replies that end with a question while the PREVIOUS
                reply in the same thread also ended with one (the re-ask-loop
                failure class). Emitted to needs_chosen.jsonl WITHOUT a chosen
                — a human (or a strong model, reviewed by a human) writes the
                delivering reply before these join the train set.

Run against the PRODUCTION DB (where the real decisions live):
    DATABASE_URL=<railway-postgres-url> python scripts/harvest_dpo.py
Local dev DB works too (mechanics test):
    python scripts/harvest_dpo.py

Output (backend/scripts/dpo_data/):
    pairs.jsonl        {prompt, chosen, rejected, source, session_id}
    needs_chosen.jsonl {prompt, rejected, source:"loop", session_id}

PRIVACY: prompts contain decrypted client text. The output is training data
for OUR model only — keep it out of git (dpo_data/ is gitignored) and push
the final dataset only to a PRIVATE HF repo.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import db_session                     # noqa: E402
from app.core.crypto import decrypt_str                   # noqa: E402
from app.db import models                                 # noqa: E402

OUT_DIR = Path(__file__).parent / "dpo_data"
OUT_DIR.mkdir(exist_ok=True)

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "")).strip().lower()


def _completion(technique: str, rationale: str, plan: str, response: str) -> str:
    """Reassemble the 4-field completion format the responder is trained on."""
    return (f"Technique: {technique or 'Supportive counselling'}\n"
            f"Rationale: {rationale or 'Chosen by the reviewing clinician.'}\n"
            f"Plan: {plan or 'Deliver the reply below.'}\n"
            f"Response: {response}")


def _thread_prompt(db, sess) -> str:
    """Conversation context up to (and including) this turn's user message —
    mirrors the shape prompt_builder feeds the responder."""
    lines = []
    if sess.conversation_id:
        prior = (db.query(models.Session)
                   .filter(models.Session.conversation_id == sess.conversation_id,
                           models.Session.created_at < sess.created_at)
                   .order_by(models.Session.created_at.asc()).all())[-4:]
        if prior:
            lines.append("[THREAD SO FAR]")
            for p in prior:
                lines.append(f"Client: {decrypt_str(p.user_input_enc)}")
                if p.final_reply_enc:
                    lines.append(f"You: {decrypt_str(p.final_reply_enc)}")
    lines.append("[CURRENT CLIENT MESSAGE]")
    lines.append(decrypt_str(sess.user_input_enc))
    lines.append("[CLINICAL TASK]\nReply as the CBT clinician in the "
                 "Technique/Rationale/Plan/Response format.")
    return "\n".join(lines)


def main() -> None:
    pairs, needs_chosen = [], []
    with db_session() as db:
        # ---- 1+2: reviewed sessions (approve / edit) -----------------------
        reviewed = (db.query(models.Session, models.ReviewQueue)
                      .join(models.ReviewQueue,
                            models.ReviewQueue.session_id == models.Session.id)
                      .filter(models.ReviewQueue.resolution.in_(["approve", "edit"]),
                              models.Session.final_reply_enc.isnot(None))
                      .all())
        for sess, queue in reviewed:
            final = decrypt_str(sess.final_reply_enc)
            if not final.strip():
                continue
            drafts = (db.query(models.Draft)
                        .filter_by(session_id=sess.id)
                        .order_by(models.Draft.idx).all())
            if not drafts:
                continue
            prompt = _thread_prompt(db, sess)
            chosen = _completion(sess.final_technique, "", "", final)
            for d in drafts:
                resp = decrypt_str(d.response_enc)
                if not resp.strip():
                    continue
                # approve: skip the draft that IS the final (it's the chosen)
                if queue.resolution == "approve" and _norm(resp) == _norm(final):
                    chosen = _completion(d.technique, d.rationale, d.plan, resp)
                    continue
                pairs.append({
                    "prompt": prompt,
                    "chosen": chosen,
                    "rejected": _completion(d.technique, d.rationale,
                                            d.plan, resp),
                    "source": queue.resolution,
                    "session_id": str(sess.id),
                })

        # ---- 3: auto-sent question-loop replies (rejected only) ------------
        auto = (db.query(models.Session)
                  .filter(models.Session.status == "auto_sent",
                          models.Session.conversation_id.isnot(None))
                  .order_by(models.Session.conversation_id,
                            models.Session.created_at).all())
        prev_by_convo = {}
        for sess in auto:
            reply = decrypt_str(sess.final_reply_enc) if sess.final_reply_enc else ""
            prev = prev_by_convo.get(sess.conversation_id, "")
            prev_by_convo[sess.conversation_id] = reply.strip()
            if not reply.strip():
                continue
            if reply.strip().endswith("?") and prev.endswith("?"):
                needs_chosen.append({
                    "prompt": _thread_prompt(db, sess),
                    "rejected": _completion(sess.final_technique, "", "", reply),
                    "source": "loop",
                    "session_id": str(sess.id),
                })

    with open(OUT_DIR / "pairs.jsonl", "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "needs_chosen.jsonl", "w", encoding="utf-8") as f:
        for p in needs_chosen:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    by_src = {}
    for p in pairs:
        by_src[p["source"]] = by_src.get(p["source"], 0) + 1
    print(f"pairs.jsonl        : {len(pairs)} pairs {by_src}")
    print(f"needs_chosen.jsonl : {len(needs_chosen)} loop replies awaiting a "
          f"hand-written chosen")
    print(f"output dir         : {OUT_DIR}")


if __name__ == "__main__":
    main()
