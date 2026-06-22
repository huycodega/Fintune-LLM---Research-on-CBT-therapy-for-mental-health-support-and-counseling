"""Idempotent demo seed for screenings so the admin Screening page / Reports
have real rows to show. Runs on startup; only inserts when the screenings
table is (near) empty, and always attaches to REAL existing users.
"""
from datetime import datetime, timezone, timedelta

from app.db import models

# Five varied, realistic PHQ-9 / GAD-7 results (score, level, gad, gad_level,
# mood, days_ago, phq9 item-9 flag).
_SAMPLES = [
    (22, "severe", 16, "severe", 2, 1, 2),
    (17, "moderately_severe", 12, "moderate", 4, 2, 1),
    (12, "moderate", 9, "mild", 5, 4, 0),
    (7, "mild", 6, "mild", 6, 6, 0),
    (3, "minimal", 2, "minimal", 8, 9, 0),
]


def _phq9_answers(score, item9):
    """A plausible 9-item answer vector (0-3) that sums to ~score, with the
    last item (suicidal ideation) set to `item9`."""
    answers = [0] * 9
    answers[8] = item9
    remaining = max(0, score - item9)
    i = 0
    while remaining > 0 and i < 8:
        step = min(3, remaining)
        answers[i] = step
        remaining -= step
        i += 1
    return answers


def seed_demo_screenings(db) -> int:
    """Insert demo screenings if the table is near-empty. Returns rows added."""
    if db.query(models.Screening).count() >= 5:
        return 0
    users = (db.query(models.User)
             .filter(models.User.role == "user")
             .order_by(models.User.created_at).limit(5).all())
    if not users:
        return 0
    now = datetime.now(timezone.utc)
    added = 0
    for idx, (phq, phq_lvl, gad, gad_lvl, mood, days, item9) in enumerate(_SAMPLES):
        user = users[idx % len(users)]
        db.add(models.Screening(
            user_id=user.id,
            created_at=now - timedelta(days=days, hours=idx),
            phq9_score=phq, phq9_level=phq_lvl, phq9_answers=_phq9_answers(phq, item9),
            gad7_score=gad, gad7_level=gad_lvl,
            gad7_answers=[min(3, gad // 7)] * 7,
            mood_score=mood,
            notes="Demo screening seeded for dashboard/reporting.",
        ))
        added += 1
    db.flush()
    return added
