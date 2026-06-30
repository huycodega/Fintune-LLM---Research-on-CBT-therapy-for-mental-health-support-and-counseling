"""
Per-user durable memory.

Distinct from `session_memory` (which embeds each finished session into
Qdrant for *semantic* recall). This module keeps a single compact,
structured record per user in Postgres — the facts the assistant should
always carry into a new turn:

  * recurring concerns / themes (from analysis)
  * techniques that have been used (and how often)
  * a short rolling gist

It is updated best-effort after each L2/L3 turn and injected into the
prompt as a "what we know about this user" block. The encrypted `facts_enc`
column holds the JSON; `summary` holds a short non-PHI gist for quick display.
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phi, decrypt_str
from app.db import models

log = logging.getLogger(__name__)

_MAX_THEMES = 8
_MAX_TECH = 8


def _load_facts(row: models.UserMemory) -> dict:
    if not row or not row.facts_enc:
        return {"themes": {}, "techniques": {}}
    try:
        return json.loads(decrypt_str(row.facts_enc))
    except Exception:
        return {"themes": {}, "techniques": {}}


def get_or_create(db: Session, user_id) -> models.UserMemory:
    row = db.query(models.UserMemory).filter_by(user_id=user_id).first()
    if row is None:
        row = models.UserMemory(user_id=user_id, turn_count=0)
        db.add(row)
        db.flush()
    return row


def load_for_prompt(db: Session, user_id) -> dict:
    """Return a small dict the prompt builder can render. Never raises."""
    try:
        row = db.query(models.UserMemory).filter_by(user_id=user_id).first()
        if not row:
            return {}
        facts = _load_facts(row)
        themes = sorted(facts.get("themes", {}).items(),
                        key=lambda kv: -kv[1])[:5]
        techs = sorted(facts.get("techniques", {}).items(),
                       key=lambda kv: -kv[1])[:5]
        return {
            "turn_count": row.turn_count,
            "summary": row.summary or "",
            "recurring_themes": [t for t, _ in themes],
            "techniques_used": [t for t, _ in techs],
        }
    except Exception as e:
        log.warning("user_memory load failed for %s: %s", user_id, e)
        return {}


def set_summary(db: Session, user_id, summary: str) -> None:
    """Overwrite ONLY the rolling gist with an LLM-written one (the structured
    themes/techniques counters are left untouched). Best-effort."""
    try:
        row = db.query(models.UserMemory).filter_by(user_id=user_id).first()
        if row and summary:
            row.summary = summary[:600]
            db.flush()
    except Exception as e:
        log.warning("user_memory set_summary failed for %s: %s", user_id, e)


def update_after_turn(db: Session, user_id, *, analysis: Optional[dict],
                      technique: Optional[str], severity: Optional[str]) -> None:
    """Accumulate compact facts. Heuristic (no LLM) so it works in mock mode.
    Best-effort: any failure is swallowed."""
    try:
        row = get_or_create(db, user_id)
        facts = _load_facts(row)
        themes = facts.setdefault("themes", {})
        techs = facts.setdefault("techniques", {})

        # themes: distortions + emotions from analyzer.analyze()
        # analyzer returns comma-separated strings under "cognitive_distortions"
        # and "emotion" (singular) — parse both into the themes counter.
        analysis = analysis or {}
        for key in ("cognitive_distortions", "emotion"):
            raw = analysis.get(key, "") or ""
            for v in raw.split(","):
                v = v.strip().lower()[:40]
                if v and v not in ("none clearly detected", "unspecified distress"):
                    themes[v] = themes.get(v, 0) + 1
        if technique:
            t = str(technique).strip().lower()[:40]
            techs[t] = techs.get(t, 0) + 1

        # cap the dicts so they don't grow unbounded
        facts["themes"] = dict(sorted(themes.items(),
                                      key=lambda kv: -kv[1])[:_MAX_THEMES])
        facts["techniques"] = dict(sorted(techs.items(),
                                          key=lambda kv: -kv[1])[:_MAX_TECH])

        top_themes = list(facts["themes"].keys())[:3]
        row.facts_enc = encrypt_phi(json.dumps(facts, ensure_ascii=False))
        row.turn_count = (row.turn_count or 0) + 1
        row.summary = (
            f"{row.turn_count} turns; recurring: "
            f"{', '.join(top_themes) if top_themes else 'n/a'}"
        )[:400]
        db.flush()
    except Exception as e:
        log.warning("user_memory update failed for %s: %s", user_id, e)
