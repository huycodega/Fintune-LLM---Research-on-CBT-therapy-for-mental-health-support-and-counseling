"""
Action intents — the user asking the assistant to DO something that writes data
(log a mood, cancel an appointment, mark a lesson done, start a screening).

This module only DETECTS the intent and PROPOSES confirm-cards; it never writes.
The chat returns the proposal as `actions` (buttons); the actual write happens
only when the user taps Confirm, which calls the EXISTING REST endpoints
(submit_screening / cancel appointment / set_lesson_progress) from the frontend.
So nothing here is destructive, and a write always needs an explicit confirm.

Safety: the chat action-gate runs only on L2/L3, never when the message carries
a distress/risk signal, and only after the safety regex clears L0/L1.
"""
import re

from app.db import models

# ── detection ────────────────────────────────────────────────────────────────
_SCREEN = re.compile(
    r"\b(do|take|start|begin|complete|fill|finish)\b.{0,20}"
    r"\b(phq[- ]?9|gad[- ]?7|screening|self[- ]?check|assessment|questionnaire)\b|"
    r"i want to (do|take|start|complete) (a |the )?"
    r"(screening|test|assessment|self[- ]?check|phq|gad)", re.I)
_RESCHED = re.compile(
    r"\b(reschedule|re-schedule)\b.{0,20}\b(appointment|booking|consultation|slot)\b|"
    r"\breschedule my (appointment|booking|consultation)\b|"
    r"\b(move|change|shift)\b.{0,20}\b(appointment|booking|consultation)\b|"
    r"\b(change|move)\b.{0,12}\b(time|date|day)\b.{0,20}\b(appointment|booking)\b|"
    r"(different|another|new) (time|slot|day) for my (appointment|booking)", re.I)
_CANCEL = re.compile(
    r"\bcancel\b.{0,20}\b(appointment|booking|consultation)\b|"
    r"\b(cancel|delete|remove) my (appointment|booking|consultation)", re.I)
_MARK = re.compile(
    r"\bmark\b.{0,25}\b(lesson|done|complete|completed|finished)\b|"
    r"i (just )?(finished|completed|did)\b.{0,25}\blesson", re.I)
_MOOD = re.compile(
    r"\b(log|record|save|track|set|update|note)\b.{0,15}\bmood\b|"
    r"\bmood\b.{0,10}\b(is|=|:)\s*(10|[1-9])\b", re.I)
_MOOD_NUM = re.compile(r"\b(10|[1-9])\b")


def detect(text: str):
    """Return an action kind, or None. Order matters: a verb-led action wins
    over the generic 'mood' word. Distress/safety guards are applied by the
    caller before this is acted on."""
    low = (text or "").lower()
    if not low:
        return None
    if _SCREEN.search(low):
        return "start_screening"
    if _RESCHED.search(low):
        return "reschedule_appt"
    if _CANCEL.search(low):
        return "cancel_appt"
    if _MARK.search(low):
        return "mark_lesson"
    if _MOOD.search(low):
        return "log_mood"
    return None


# ── proposal (confirm-cards) ─────────────────────────────────────────────────
def propose(db, uid, kind: str, text: str):
    """Return (reply_text, actions) where actions is a list of confirm-cards the
    UI renders with a [Confirm] button. Read-only — no writes happen here."""
    if kind == "start_screening":
        low = (text or "").lower()
        instr = ("PHQ-9" if "phq" in low else
                 "GAD-7" if "gad" in low else "a quick self-check")
        return (f"Sure — you can take {instr} on the Screening page whenever "
                "you're ready.",
                [{"kind": "navigate", "section": "sangloc",
                  "label": f"Open {instr}"}])

    if kind == "log_mood":
        m = _MOOD_NUM.search(text or "")
        if not m:
            return ("Of course — how would you rate your mood right now on a "
                    "scale of 1 to 10? (e.g. \"log my mood as 7\")", [])
        v = int(m.group(1))
        return (f"Want me to log today's mood as {v}/10?",
                [{"kind": "log_mood", "value": v,
                  "label": f"Log mood {v}/10"}])

    if kind in ("cancel_appt", "reschedule_appt"):
        # Both the cancel and change endpoints only allow PENDING appointments.
        rows = (db.query(models.Appointment, models.Psychologist)
                .join(models.Psychologist,
                      models.Appointment.psychologist_id == models.Psychologist.id)
                .filter(models.Appointment.user_id == uid,
                        models.Appointment.status == "pending")
                .order_by(models.Appointment.date).all())
        verb = "cancel" if kind == "cancel_appt" else "reschedule"
        if not rows:
            return (f"You have no pending appointments to {verb}.", [])
        acts = []
        for a, p in rows:
            item = {"kind": kind, "appointment_id": str(a.id),
                    "label": f"{verb.capitalize()} {a.date.isoformat()} "
                             f"{a.slot} with {p.name}"}
            if kind == "reschedule_appt":
                item["psychologist_id"] = str(a.psychologist_id)
                item["name"] = p.name
            acts.append(item)
        return (f"Which appointment would you like to {verb}?", acts)

    if kind == "mark_lesson":
        rows = (db.query(models.UserLessonProgress, models.Lesson)
                .join(models.Lesson,
                      models.UserLessonProgress.lesson_id == models.Lesson.id)
                .filter(models.UserLessonProgress.user_id == uid,
                        models.UserLessonProgress.status != "completed")
                .order_by(models.UserLessonProgress.updated_at.desc())
                .limit(10).all())
        if not rows:
            return ("You don't have any lessons in progress to mark as done. "
                    "Open the Lessons page to start one.", [])
        acts = [{"kind": "mark_lesson", "lesson_id": str(l.id),
                 "label": f"Mark '{l.title}' as done"} for p, l in rows]
        return ("Which lesson did you finish?", acts)

    return ("", [])
