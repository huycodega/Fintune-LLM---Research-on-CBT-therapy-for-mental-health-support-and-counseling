"""
Wellness roadmaps — time-bound improvement journeys.

When the client asks for a plan over a stretch of time ("a 2-week plan to
sleep better", "help me build a routine over the next month"), the agent
drafts a structured roadmap: a title, the timeframe, and 5-8 concrete steps
distributed across it. The client then works through it step by step; each
completion is timestamped so the journey can be charted. Many roadmaps per
user, agent-drafted + client-owned.

    rm = roadmap.generate(goal, timeframe, history)   # dict
    rid = roadmap.save(db, user_id, rm)
    roadmap.load_all(db, user_id)                     # list + progress
    roadmap.toggle_step(db, user_id, rid, idx)
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.crypto import decrypt_str, encrypt_phi
from app.db import models
from app.services import llm_client

log = logging.getLogger(__name__)

_SYS = (
    "You are a CBT clinician designing a short, encouraging WELLNESS ROADMAP "
    "for a student — a time-bound journey of small, concrete steps toward "
    "their goal. Given the goal and timeframe, output STRICT JSON:\n"
    '  "title": a short motivating title (<=60 chars);\n'
    '  "timeframe": echo the timeframe as a short label (e.g. "2 weeks");\n'
    '  "steps": a list of 5-8 objects, each {"text": one concrete, doable '
    'action in first person (<=120 chars), "when": a short time marker within '
    'the timeframe (e.g. "Day 1-2", "Week 1", "Daily")}. \n'
    "Order steps from easiest/earliest to more involved. Ground them in CBT "
    "and healthy routines (sleep, activity, thought records, small exposures, "
    "connection). Do NOT invent facts about the student. Output ONLY the JSON."
)

_FALLBACK = {
    "title": "A steadier two weeks",
    "timeframe": "2 weeks",
    "steps": [
        {"text": "Pick one fixed wake-up time and keep it every day", "when": "Daily"},
        {"text": "Do 5 minutes of slow breathing each morning", "when": "Daily"},
        {"text": "Write down one worry and one piece of counter-evidence", "when": "Day 1-3"},
        {"text": "Take a 15-minute walk outside three times", "when": "Week 1"},
        {"text": "Message one person I trust to check in", "when": "Week 1"},
        {"text": "Try one small thing I've been avoiding", "when": "Week 2"},
        {"text": "Review what helped and note it down", "when": "Week 2"},
    ],
}

# Intent: an explicit request for a time-bound plan/routine/journey.
_INTENT = re.compile(
    r"\b(\d+\s*(day|days|week|weeks|month|months|hour|hours))\b.{0,40}"
    r"(plan|routine|roadmap|schedule|program|journey|steps?)|"
    r"\b(plan|routine|roadmap|schedule|program|journey)\b.{0,40}"
    r"(over|for|across|in)\s+(the\s+)?(next\s+)?\d*\s*"
    r"(day|days|week|weeks|month|months|hour|hours)|"
    r"\bstep[- ]by[- ]step (plan|routine|program)|"
    r"\b(build|make|create|give me|set up) (me )?a (daily|weekly|"
    r"\d+[- ](day|week|month)) (plan|routine|program|roadmap)", re.I)

_TF = re.compile(
    r"(\d+)\s*(hour|hours|day|days|week|weeks|month|months)", re.I)


def wants_roadmap(text: str) -> bool:
    return bool(_INTENT.search(text or ""))


def parse_timeframe(text: str) -> str:
    m = _TF.search(text or "")
    if m:
        n, unit = m.group(1), m.group(2).lower().rstrip("s")
        return f"{n} {unit}{'s' if n != '1' else ''}"
    return "2 weeks"


def generate(goal: str, timeframe: str, history: List[str] = None) -> Dict:
    """Draft a roadmap. Always returns a valid structure (fallback on error)."""
    rm = json.loads(json.dumps(_FALLBACK))       # deep copy
    rm["timeframe"] = timeframe or rm["timeframe"]
    ctx = "\n".join(h for h in (history or []) if h)[:1500]
    try:
        gen = llm_client.generate(
            [{"role": "system", "content": _SYS},
             {"role": "user",
              "content": f"[GOAL]\n{goal}\n[TIMEFRAME]\n{timeframe}\n"
                         + (f"[CONTEXT]\n{ctx}\n" if ctx else "")
                         + "\nDraft the JSON roadmap."}],
            n=1, temperature=0.4)
        if gen and not gen.get("degraded") and gen.get("mode") != "mock":
            raw = (gen.get("responses") or [""])[0]
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                parsed = json.loads(m.group())
                steps = parsed.get("steps")
                if isinstance(steps, list) and steps:
                    rm["title"] = str(parsed.get("title") or rm["title"])[:80]
                    rm["timeframe"] = str(parsed.get("timeframe")
                                          or timeframe)[:40]
                    rm["steps"] = [
                        {"text": str(s.get("text", "")).strip()[:200],
                         "when": str(s.get("when", "")).strip()[:40]}
                        for s in steps[:8] if str(s.get("text", "")).strip()]
    except Exception as e:
        log.warning("roadmap generate failed (%s) — fallback", e)
    rm["goal"] = (goal or "").strip()[:300]
    # normalise step state
    for s in rm["steps"]:
        s.setdefault("done", False)
        s.setdefault("done_at", None)
    return rm


def _progress(rm: Dict) -> Dict:
    steps = rm.get("steps") or []
    total = len(steps)
    done = sum(1 for s in steps if s.get("done"))
    return {"total": total, "done": done,
            "pct": round(done / total * 100) if total else 0}


def _public(row: models.Roadmap) -> Optional[Dict]:
    try:
        rm = json.loads(decrypt_str(row.content_enc))
    except Exception as e:
        log.warning("roadmap decrypt failed %s: %s", row.id, e)
        return None
    rm["id"] = str(row.id)
    rm["status"] = row.status
    rm["created_at"] = row.created_at.isoformat() if row.created_at else None
    rm["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    rm["progress"] = _progress(rm)
    return rm


def save(db, user_id, rm: Dict) -> str:
    body = {k: rm[k] for k in ("title", "goal", "timeframe", "steps")
            if k in rm}
    row = models.Roadmap(
        user_id=user_id, status="active",
        content_enc=encrypt_phi(json.dumps(body, ensure_ascii=False)))
    db.add(row); db.flush()
    return str(row.id)


def load_all(db, user_id) -> List[Dict]:
    rows = (db.query(models.Roadmap)
              .filter_by(user_id=user_id)
              .order_by(models.Roadmap.created_at.desc()).all())
    return [r for r in (_public(x) for x in rows) if r]


def load_one(db, user_id, rid) -> Optional[Dict]:
    row = (db.query(models.Roadmap)
             .filter_by(id=rid, user_id=user_id).first())
    return _public(row) if row else None


def _write_back(db, row, rm: Dict) -> None:
    body = {k: rm[k] for k in ("title", "goal", "timeframe", "steps")
            if k in rm}
    row.content_enc = encrypt_phi(json.dumps(body, ensure_ascii=False))
    row.updated_at = datetime.now(timezone.utc)
    db.flush()


def toggle_step(db, user_id, rid, idx: int) -> Optional[Dict]:
    row = db.query(models.Roadmap).filter_by(id=rid, user_id=user_id).first()
    if not row:
        return None
    rm = json.loads(decrypt_str(row.content_enc))
    steps = rm.get("steps") or []
    if 0 <= idx < len(steps):
        now_done = not steps[idx].get("done")
        steps[idx]["done"] = now_done
        steps[idx]["done_at"] = (datetime.now(timezone.utc).isoformat()
                                 if now_done else None)
    rm["steps"] = steps
    _write_back(db, row, rm)
    # auto-complete the roadmap when every step is done
    if steps and all(s.get("done") for s in steps):
        row.status = "completed"
        db.flush()
    elif row.status == "completed":
        row.status = "active"
        db.flush()
    return _public(row)


def set_status(db, user_id, rid, status: str) -> Optional[Dict]:
    if status not in ("active", "completed", "archived"):
        return None
    row = db.query(models.Roadmap).filter_by(id=rid, user_id=user_id).first()
    if not row:
        return None
    row.status = status
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return _public(row)


def delete(db, user_id, rid) -> bool:
    row = db.query(models.Roadmap).filter_by(id=rid, user_id=user_id).first()
    if not row:
        return False
    db.delete(row); db.flush()
    return True
