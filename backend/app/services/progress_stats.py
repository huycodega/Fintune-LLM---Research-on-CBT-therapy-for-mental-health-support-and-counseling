"""
Progress statistics shared by the user Profile (/me/overview) and the admin
user-detail view — one source of truth so both sides read the same numbers.

  lessons_done   : CBT lessons/exercises the user completed, newest first
  common_themes  : most frequent emotions + cognitive distortions across chats
  stress_trend   : PHQ-9/GAD-7 series + a plain-language direction label
"""
from collections import Counter
from typing import Dict, List

from app.db import models


def lessons_done(db, uid, limit: int = 10) -> List[Dict]:
    rows = (db.query(models.UserLessonProgress, models.Lesson)
            .join(models.Lesson,
                  models.Lesson.id == models.UserLessonProgress.lesson_id)
            .filter(models.UserLessonProgress.user_id == uid,
                    models.UserLessonProgress.status == "completed")
            .order_by(models.UserLessonProgress.updated_at.desc())
            .limit(limit).all())
    return [{
        "title": lesson.title,
        "category": getattr(lesson, "category", None),
        "completed_at": (prog.updated_at.isoformat()
                         if prog.updated_at else None),
    } for prog, lesson in rows]


def common_themes(db, uid, top: int = 5) -> List[Dict]:
    """Top recurring themes from the analyzer output stored on each session
    (emotions + cognitive distortions, both comma-joined strings)."""
    rows = (db.query(models.Session.analysis)
            .filter(models.Session.user_id == uid,
                    models.Session.analysis.isnot(None)).all())
    counts: Counter = Counter()
    for (analysis,) in rows:
        if not isinstance(analysis, dict):
            continue
        for key in ("emotion", "cognitive_distortions"):
            for item in str(analysis.get(key) or "").split(","):
                item = item.strip().lower()
                if item and item not in ("none", "unknown", "-"):
                    counts[item] += 1
    return [{"theme": t, "count": c} for t, c in counts.most_common(top)]


def stress_trend(db, uid, limit: int = 12) -> Dict:
    """Screening series (oldest→newest) + direction. Lower scores are better,
    so a falling combined score reads as 'improving'."""
    rows = (db.query(models.Screening)
            .filter(models.Screening.user_id == uid)
            .order_by(models.Screening.created_at.desc())
            .limit(limit).all())[::-1]
    points = [{
        "date": s.created_at.isoformat() if s.created_at else None,
        "phq9": s.phq9_score,
        "gad7": s.gad7_score,
    } for s in rows]

    scored = [(p["phq9"] or 0) + (p["gad7"] or 0)
              for p in points if p["phq9"] is not None or p["gad7"] is not None]
    direction = None
    if len(scored) >= 2:
        prev = sum(scored[:-1]) / len(scored[:-1])
        delta = scored[-1] - prev
        direction = ("improving" if delta <= -2
                     else "worsening" if delta >= 2 else "stable")
    return {"points": points, "direction": direction}
