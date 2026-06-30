"""
Self-data lookups — a user's OWN MindCare records, formatted as a short, direct
reply. Pure read-only helpers shared by:

  • the chat "direct-answer gate" (answers factual questions like "who am I" /
    "my appointments" instantly, without a CBT draft or clinician review), and
  • the agent's get_my_data / list_psychologists tools,

so both surface IDENTICAL, real data — never fabricated. Nothing here is PHI
beyond the user's own account, which is being returned to that same user.
"""
from __future__ import annotations

from app.db import models


def profile(db, uid) -> str:
    u = db.get(models.User, uid)
    if not u:
        return "I couldn't find your profile."
    joined = u.created_at.date().isoformat() if u.created_at else "—"
    return f"You're signed in as {u.username}, a MindCare member since {joined}."


def appointments(db, uid) -> str:
    rows = (db.query(models.Appointment, models.Psychologist)
            .join(models.Psychologist,
                  models.Appointment.psychologist_id == models.Psychologist.id)
            .filter(models.Appointment.user_id == uid)
            .order_by(models.Appointment.date.desc()).limit(10).all())
    if not rows:
        return "You have no appointments booked yet."
    items = [f"- {a.date.isoformat()} {a.slot} with {p.name} — {a.status}"
             for a, p in rows]
    return "Here are your appointments:\n" + "\n".join(items)


def lessons(db) -> str:
    rows = (db.query(models.Lesson).filter_by(status="published")
            .order_by(models.Lesson.updated_at.desc()).limit(8).all())
    if not rows:
        return "There are no lessons available yet."
    items = [f"- {x.title}" + (f" ({x.duration})" if x.duration else "")
             for x in rows]
    return "Here are the lessons available:\n" + "\n".join(items)


def psychologists(db) -> str:
    rows = (db.query(models.Psychologist).filter_by(active=True)
            .order_by(models.Psychologist.name).limit(10).all())
    if not rows:
        return "No counselling experts are listed yet."
    items = []
    for p in rows:
        bits = [p.name]
        if p.specialty:
            bits.append(p.specialty)
        if p.experience:
            bits.append(p.experience)
        items.append("- " + " — ".join(bits))
    return "Here are the counselling experts you can book:\n" + "\n".join(items)


def mood(db, uid) -> str:
    rows = (db.query(models.Screening)
            .filter(models.Screening.user_id == uid,
                    models.Screening.mood_score.isnot(None))
            .order_by(models.Screening.created_at.desc()).limit(5).all())
    if not rows:
        return "You haven't recorded any mood check-ins yet."
    latest = rows[0]
    trend = ", ".join(str(r.mood_score) for r in reversed(rows))
    return (f"Your latest mood is {latest.mood_score}/10 "
            f"({latest.created_at.date().isoformat()}). Recent: {trend}.")


def screening(db, uid) -> str:
    rows = (db.query(models.Screening)
            .filter(models.Screening.user_id == uid)
            .order_by(models.Screening.created_at.desc()).limit(5).all())
    lines = []
    for r in rows:
        d = r.created_at.date().isoformat()
        parts = []
        if r.phq9_score is not None:
            parts.append(f"PHQ-9 {r.phq9_score}"
                         + (f" ({r.phq9_level})" if r.phq9_level else ""))
        if r.gad7_score is not None:
            parts.append(f"GAD-7 {r.gad7_score}"
                         + (f" ({r.gad7_level})" if r.gad7_level else ""))
        if parts:
            lines.append(f"- {d}: " + ", ".join(parts))
    if not lines:
        return "You don't have any PHQ-9 / GAD-7 results yet."
    return "Here is your screening history:\n" + "\n".join(lines)
