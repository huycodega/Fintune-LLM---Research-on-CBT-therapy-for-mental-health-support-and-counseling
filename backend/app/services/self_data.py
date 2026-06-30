"""
Self-data lookups — a user's OWN MindCare records, as both a text reply and
structured "cards" the chat UI can render as interactive (tappable) items.

Shared by:
  • the chat direct-answer gate (answers "who am I" / "my appointments" /
    "what lessons are there" instantly — text for history + cards for the UI),
  • the agent's get_my_data / list_psychologists tools (text only).

The *_cards functions return plain dicts (real records only, never fabricated);
the text functions format from them so the two never drift.
"""
from __future__ import annotations

from app.db import models


# ── structured (for interactive UI cards) ────────────────────────────────────
def lessons_cards(db) -> list:
    rows = (db.query(models.Lesson).filter_by(status="published")
            .order_by(models.Lesson.updated_at.desc()).limit(8).all())
    return [{"id": str(x.id), "title": x.title, "duration": x.duration,
             "category": x.category} for x in rows]


def resources_cards(db) -> list:
    rows = (db.query(models.Resource).filter_by(status="published")
            .order_by(models.Resource.updated_at.desc()).limit(8).all())
    return [{"id": str(x.id), "title": x.title, "type": x.type,
             "category": x.category} for x in rows]


def psychologists_cards(db) -> list:
    rows = (db.query(models.Psychologist).filter_by(active=True)
            .order_by(models.Psychologist.name).limit(10).all())
    return [{"id": str(p.id), "name": p.name, "specialty": p.specialty,
             "experience": p.experience, "phone": p.phone} for p in rows]


def appointments_cards(db, uid) -> list:
    rows = (db.query(models.Appointment, models.Psychologist)
            .join(models.Psychologist,
                  models.Appointment.psychologist_id == models.Psychologist.id)
            .filter(models.Appointment.user_id == uid)
            .order_by(models.Appointment.date.desc()).limit(10).all())
    return [{"date": a.date.isoformat(), "slot": a.slot, "name": p.name,
             "status": a.status} for a, p in rows]


# ── text (for the reply body + agent footer + history) ───────────────────────
def profile(db, uid) -> str:
    u = db.get(models.User, uid)
    if not u:
        return "I couldn't find your profile."
    joined = u.created_at.date().isoformat() if u.created_at else "—"
    return f"You're signed in as {u.username}, a MindCare member since {joined}."


def appointments(db, uid) -> str:
    items = appointments_cards(db, uid)
    if not items:
        return "You have no appointments booked yet."
    rows = [f"- {a['date']} {a['slot']} with {a['name']} — {a['status']}"
            for a in items]
    return "Here are your appointments:\n" + "\n".join(rows)


def lessons(db) -> str:
    items = lessons_cards(db)
    if not items:
        return "There are no lessons available yet."
    rows = [f"- {x['title']}" + (f" ({x['duration']})" if x['duration'] else "")
            for x in items]
    return "Here are the lessons available — tap one to open it:\n" + "\n".join(rows)


def resources(db) -> str:
    items = resources_cards(db)
    if not items:
        return "There are no support resources available yet."
    rows = [f"- {x['title']}" + (f" [{x['type']}]" if x['type'] else "")
            for x in items]
    return ("Here are the support resources available — tap one to open it:\n"
            + "\n".join(rows))


def psychologists(db) -> str:
    items = psychologists_cards(db)
    if not items:
        return "No counselling experts are listed yet."
    rows = []
    for p in items:
        bits = [p["name"]]
        if p["specialty"]:
            bits.append(p["specialty"])
        if p["experience"]:
            bits.append(p["experience"])
        rows.append("- " + " — ".join(bits))
    return ("Here are the counselling experts you can book — tap one to see "
            "their times:\n" + "\n".join(rows))


def lesson_progress(db, uid) -> str:
    rows = (db.query(models.UserLessonProgress, models.Lesson)
            .join(models.Lesson,
                  models.UserLessonProgress.lesson_id == models.Lesson.id)
            .filter(models.UserLessonProgress.user_id == uid)
            .order_by(models.UserLessonProgress.updated_at.desc()).limit(10).all())
    if not rows:
        return "You haven't started any lessons yet."
    done = sum(1 for p, _ in rows if p.status == "completed")
    lines = [f"- {l.title}: {p.progress_pct}%"
             + (" ✓ done" if p.status == "completed" else "")
             for p, l in rows]
    return f"Your lesson progress ({done} completed):\n" + "\n".join(lines)


def recall(db, uid) -> str:
    from app.services import user_memory
    mem = user_memory.load_for_prompt(db, uid)
    if not mem or not mem.get("turn_count"):
        return ("We haven't talked before yet — this looks like an early "
                "conversation. What's on your mind today?")
    themes = ", ".join(mem.get("recurring_themes") or []) or "—"
    out = (f"So far we've had {mem.get('turn_count')} sessions together. "
           f"Recurring themes: {themes}.")
    summary = (mem.get("summary") or "").strip()
    if summary:
        out += f"\n{summary}"
    return out


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
