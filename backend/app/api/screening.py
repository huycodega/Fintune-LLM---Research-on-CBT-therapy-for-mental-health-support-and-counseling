"""
Screening API — periodic PHQ-9 / GAD-7 mental health check-ins.
Users can submit results multiple times; history is returned newest-first.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import auth
from app.db import models
from app.db.session import get_db

router = APIRouter(prefix="/api")


def _phq9_level(score: int) -> str:
    if score <= 4:  return "normal"
    if score <= 9:  return "mild"
    if score <= 14: return "moderate"
    if score <= 19: return "moderately_severe"
    return "severe"


def _gad7_level(score: int) -> str:
    if score <= 4:  return "normal"
    if score <= 9:  return "mild"
    if score <= 14: return "moderate"
    return "severe"


LEVEL_VN = {
    "normal":             "Bình thường",
    "mild":               "Nhẹ",
    "moderate":           "Vừa phải",
    "moderately_severe":  "Trung bình nặng",
    "severe":             "Nặng",
}


class ScreeningIn(BaseModel):
    phq9_answers: Optional[List[int]] = Field(None, description="9 answers, each 0-3")
    gad7_answers: Optional[List[int]] = Field(None, description="7 answers, each 0-3")
    mood_score:   Optional[int]       = Field(None, ge=1, le=10)
    notes:        Optional[str]       = None


class ScreeningOut(BaseModel):
    id:            str
    created_at:    datetime
    phq9_score:    Optional[int]
    phq9_level:    Optional[str]
    phq9_level_vn: Optional[str]
    gad7_score:    Optional[int]
    gad7_level:    Optional[str]
    gad7_level_vn: Optional[str]
    mood_score:    Optional[int]
    notes:         Optional[str]


def _to_out(s: models.Screening) -> ScreeningOut:
    return ScreeningOut(
        id=str(s.id),
        created_at=s.created_at,
        phq9_score=s.phq9_score,
        phq9_level=s.phq9_level,
        phq9_level_vn=LEVEL_VN.get(s.phq9_level or "", None),
        gad7_score=s.gad7_score,
        gad7_level=s.gad7_level,
        gad7_level_vn=LEVEL_VN.get(s.gad7_level or "", None),
        mood_score=s.mood_score,
        notes=s.notes,
    )


@router.post("/screening", response_model=ScreeningOut)
def submit_screening(
    body: ScreeningIn,
    user: dict = Depends(auth.current_user),
    db: Session = Depends(get_db),
):
    phq9_score = None
    phq9_level = None
    if body.phq9_answers:
        if len(body.phq9_answers) != 9:
            raise HTTPException(400, "phq9_answers must have exactly 9 items")
        if any(v not in range(4) for v in body.phq9_answers):
            raise HTTPException(400, "phq9_answers values must be 0-3")
        phq9_score = sum(body.phq9_answers)
        phq9_level = _phq9_level(phq9_score)

    gad7_score = None
    gad7_level = None
    if body.gad7_answers:
        if len(body.gad7_answers) != 7:
            raise HTTPException(400, "gad7_answers must have exactly 7 items")
        if any(v not in range(4) for v in body.gad7_answers):
            raise HTTPException(400, "gad7_answers values must be 0-3")
        gad7_score = sum(body.gad7_answers)
        gad7_level = _gad7_level(gad7_score)

    row = models.Screening(
        user_id=user["uid"],
        phq9_score=phq9_score,
        phq9_answers=body.phq9_answers,
        gad7_score=gad7_score,
        gad7_answers=body.gad7_answers,
        phq9_level=phq9_level,
        gad7_level=gad7_level,
        mood_score=body.mood_score,
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get("/screening/history", response_model=List[ScreeningOut])
def get_screening_history(
    limit: int = 20,
    user: dict = Depends(auth.current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Screening)
        .filter_by(user_id=user["uid"])
        .order_by(models.Screening.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_to_out(r) for r in rows]


@router.get("/screening/latest", response_model=Optional[ScreeningOut])
def get_latest_screening(
    user: dict = Depends(auth.current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.Screening)
        .filter_by(user_id=user["uid"])
        .order_by(models.Screening.created_at.desc())
        .first()
    )
    return _to_out(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# GET /screening/today — a context- & memory-aware recommendation for which
# validated instrument to take today, with a personalised intro. The SCORING
# stays the standard PHQ-9 / GAD-7; only the choice + framing is personalised.
# Deterministic + instant (no model call on page load).
# ─────────────────────────────────────────────────────────────────────────────
_ANX_WORDS = ("anxi", "panic", "worry", "worried", "nervous", "overwhelm", "stress", "fear")
_DEP_WORDS = ("depress", "sad", "hopeless", "empty", "worthless", "numb", "low mood", "exhaust")


@router.get("/screening/today")
def screening_today(user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    uid = user["uid"]
    mem = db.query(models.UserMemory).filter_by(user_id=uid).first()
    summary = (mem.summary or "").lower() if mem else ""
    recent = (db.query(models.Session)
              .filter_by(user_id=uid)
              .order_by(models.Session.created_at.desc()).limit(10).all())
    last = (db.query(models.Screening)
            .filter_by(user_id=uid)
            .order_by(models.Screening.created_at.desc()).first())

    now = datetime.now(timezone.utc)
    done_today = bool(last and last.created_at and _as_utc(last.created_at).date() == now.date())
    days_since = ((now - _as_utc(last.created_at)).days
                  if last and last.created_at else None)

    # Signals from recent sessions + memory.
    high_risk = any(s.triage_level in ("L0", "L1") for s in recent)
    anx = any(w in summary for w in _ANX_WORDS)
    dep = any(w in summary for w in _DEP_WORDS)

    # Choose the instrument: lean to the signalled area; otherwise alternate from
    # the last one taken so we track both over time.
    if dep and not anx:
        instrument, reason = "phq9", "Recent chats touched on low mood, so a quick depression check helps track it."
    elif anx and not dep:
        instrument, reason = "gad7", "Recent chats touched on anxiety, so a quick anxiety check helps track it."
    elif last and last.gad7_score is not None and last.phq9_score is None:
        instrument, reason = "phq9", "Last time you did an anxiety check — let's balance it with a depression check today."
    elif last and last.phq9_score is not None and last.gad7_score is None:
        instrument, reason = "gad7", "Last time you did a depression check — let's balance it with an anxiety check today."
    else:
        instrument, reason = ("phq9" if not last else ("gad7" if last.phq9_score is not None else "phq9")), \
            "A regular check-in helps you and your clinician see how you're doing over time."

    if high_risk:
        reason = "Some recent messages raised a safety concern — a check-in now is especially helpful."

    # Personalised, memory-aware intro (deterministic — no model call so the page
    # is instant; the recurring themes come straight from the user's memory).
    theme = (mem.summary.strip() if mem and mem.summary else "")
    if theme:
        intro = f"Based on what you've shared recently — “{theme[:160]}” — here's a short check-in for today."
    else:
        intro = "Here's a short, private check-in to see how you're doing today."

    title = {"phq9": "Depression check-in (PHQ-9)",
             "gad7": "Anxiety check-in (GAD-7)"}[instrument]

    return {
        "instrument": instrument,
        "title": title,
        "intro": intro,
        "reason": reason,
        "done_today": done_today,
        "days_since_last": days_since,
        "high_risk": high_risk,
    }
