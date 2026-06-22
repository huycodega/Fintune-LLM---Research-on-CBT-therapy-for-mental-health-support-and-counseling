"""Personalised, per-day screening planner.

Picks which VALIDATED instrument (PHQ-9 / GAD-7) to focus on today from the
user's memory + recent session signals, and a personalised intro/reason.
Scoring stays the standard instrument — this only steers the choice + framing.

- `get_or_create(db, uid, day)` is deterministic + instant (no model call), and
  caches one row per (user, day) in `screening_plans`.
- `generate_ai_intro(uid, day)` runs best-effort in the background to replace the
  intro with a model-written one (cached so it's done once per day).
- `sweep(db)` pre-creates today's plan for recently-active users (cron).
"""
import logging
from datetime import datetime, timezone, timedelta

from app.core.crypto import decrypt_str
from app.db import models
from app.db.session import db_session

log = logging.getLogger("cbt.screening_planner")

_ANX = ("anxi", "panic", "worry", "worried", "nervous", "overwhelm", "stress", "fear")
_DEP = ("depress", "sad", "hopeless", "empty", "worthless", "numb", "low mood", "exhaust")

TITLES = {"phq9": "Depression check-in (PHQ-9)", "gad7": "Anxiety check-in (GAD-7)"}

# The generic, no-signal fallback. Recorded verbatim so get_or_create can tell
# "this plan was the default" and refresh it if real signals appear later today.
_DEFAULT_REASON = "A regular check-in helps you and your clinician see how you're doing over time."


def _signals(db, uid):
    mem = db.query(models.UserMemory).filter_by(user_id=uid).first()
    summary = (mem.summary or "") if mem else ""
    recent = (db.query(models.Session).filter_by(user_id=uid)
              .order_by(models.Session.created_at.desc()).limit(10).all())
    last = (db.query(models.Screening).filter_by(user_id=uid)
            .order_by(models.Screening.created_at.desc()).first())

    # Build a corpus from the memory gist PLUS the actual recent user inputs
    # (decrypted in-backend). Relying on the analyzer's theme wording landing in
    # the summary string was too fragile — scan what the user really wrote.
    corpus = [summary.lower()]
    for s in recent:
        try:
            if s.user_input_enc:
                corpus.append(decrypt_str(s.user_input_enc).lower())
        except Exception:                                    # noqa: BLE001
            pass
    blob = " ".join(corpus)
    anx_score = sum(blob.count(w) for w in _ANX)
    dep_score = sum(blob.count(w) for w in _DEP)

    return {
        "summary": summary,
        "anx": anx_score > 0,
        "dep": dep_score > 0,
        "anx_score": anx_score,
        "dep_score": dep_score,
        "high_risk": any(s.triage_level in ("L0", "L1") for s in recent),
        "last": last,
    }


def _choose(sig) -> tuple[str, str]:
    last = sig["last"]
    a, d = sig.get("anx_score", 0), sig.get("dep_score", 0)
    if a or d:
        if a > d:
            return "gad7", "Your recent chats leaned toward anxiety, so an anxiety check helps you track it."
        if d > a:
            return "phq9", "Your recent chats leaned toward low mood, so a depression check helps you track it."
        # Both present, equal weight → alternate against last time, mention both.
        if last and last.gad7_score is not None and last.phq9_score is None:
            return "phq9", "Recent chats touched on both anxiety and low mood — last time was anxiety, so let's check your mood today."
        return "gad7", "Recent chats touched on both anxiety and low mood — let's start with an anxiety check today."
    # No content signal → alternate with the last instrument so coverage rotates.
    if last and last.gad7_score is not None and last.phq9_score is None:
        return "phq9", "Last time you did an anxiety check — let's balance it with a depression check today."
    if last and last.phq9_score is not None and last.gad7_score is None:
        return "gad7", "Last time you did a depression check — let's balance it with an anxiety check today."
    return "phq9", _DEFAULT_REASON


def _intro(sig) -> str:
    theme = (sig["summary"] or "").strip()
    if theme:
        return (f"Based on what you've shared recently — “{theme[:160]}” — "
                f"here's a short, private check-in for today.")
    return "Here's a short, private check-in to see how you're doing today."


def _apply(plan, sig):
    instrument, reason = _choose(sig)
    if sig["high_risk"]:
        reason = "Some recent messages raised a safety concern — a check-in now is especially helpful."
    plan.instrument = instrument
    plan.reason = reason
    plan.intro = _intro(sig)
    return plan


def get_or_create(db, uid, day=None):
    day = day or datetime.now(timezone.utc).date()
    plan = (db.query(models.ScreeningPlan)
            .filter_by(user_id=uid, plan_date=day).first())
    if plan:
        # A plan created before the user chatted gets cached as the generic
        # default. If real signals have since appeared today, refresh it once so
        # the recommendation actually reflects them (and let the AI intro
        # regenerate for the new focus).
        if plan.reason == _DEFAULT_REASON:
            sig = _signals(db, uid)
            if sig["anx"] or sig["dep"] or sig["high_risk"]:
                _apply(plan, sig)
                plan.ai_intro = None
                db.flush()
        return plan
    plan = models.ScreeningPlan(user_id=uid, plan_date=day, instrument="phq9")
    _apply(plan, _signals(db, uid))
    db.add(plan)
    db.flush()
    return plan


def generate_ai_intro(uid, day=None):
    """Best-effort: replace the deterministic intro with a model-written one.
    Cached — only runs when ai_intro is still empty. Never raises."""
    from app.services import llm_client
    day = day or datetime.now(timezone.utc).date()
    try:
        with db_session() as db:
            plan = (db.query(models.ScreeningPlan)
                    .filter_by(user_id=uid, plan_date=day).first())
            if not plan or plan.ai_intro:
                return
            mem = db.query(models.UserMemory).filter_by(user_id=uid).first()
            summary = (mem.summary or "").strip() if mem else ""
            instrument = plan.instrument
        kind = "anxiety (GAD-7)" if instrument == "gad7" else "low mood (PHQ-9)"
        sys = ("You write a single warm, 1-2 sentence intro inviting a user to a "
               "short mental-health self-check. Be gentle, non-clinical, non-diagnostic. "
               "No emojis. Reference their situation only if context is given.")
        usr = (f"Today's check-in is for {kind}. "
               + (f"What they've shared recently: \"{summary[:300]}\". " if summary else "")
               + "Write just the intro sentence(s).")
        gen = llm_client.generate(
            [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            n=1, temperature=0.6)
        text = (gen.get("responses") or [""])[0].strip()
        if not text or gen.get("degraded"):
            return
        text = text.strip().strip('"')[:400]
        with db_session() as db:
            plan = (db.query(models.ScreeningPlan)
                    .filter_by(user_id=uid, plan_date=day).first())
            if plan and not plan.ai_intro:
                plan.ai_intro = text
        log.info("AI screening intro generated for %s", uid)
    except Exception as e:                                   # noqa: BLE001
        log.warning("AI screening intro failed: %s", e)


def sweep(db) -> int:
    """Pre-create today's plan for users active in the last 14 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    active = (db.query(models.User.id)
              .filter(models.User.role == "user")
              .filter((models.User.last_login >= cutoff) |
                      (models.User.last_login.is_(None)))
              .all())
    n = 0
    for (uid,) in active:
        try:
            get_or_create(db, uid)
            n += 1
        except Exception as e:                               # noqa: BLE001
            log.warning("sweep plan failed for %s: %s", uid, e)
    return n
