"""
Self-service profile / settings / overview for the logged-in user.

Backs the user app's Profile, Settings, Home (activity + streak) and the
Resources bookmark toggle with REAL data. Reuses the existing `user_profiles`
table (app.db.models_admin.UserProfile) — sensitive fields (full name, phone,
DOB, emergency contact) stay AES-256-GCM encrypted in the *_enc columns;
preferences / consent / wellness goal use the columns added by migration 0011.

  GET/PUT  /api/me/profile
  GET/PUT  /api/me/settings
  POST     /api/me/password
  GET      /api/me/overview          (stats + streak + recent activity)
  GET      /api/me/saved-resources
  POST/DEL /api/me/saved-resources/{rid}
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.core.crypto import encrypt_phi, decrypt_str
from app.db import models, models_admin
from app.db.session import get_db
from app.services import (progress_stats, safety_plan as safety_plan_svc,
                          roadmap as roadmap_svc)

router = APIRouter(prefix="/api/me")


# ── Wellness roadmaps ────────────────────────────────────────────────────────
class RoadmapIn(BaseModel):
    goal: str
    timeframe: Optional[str] = None


@router.get("/roadmaps")
def list_roadmaps(user: dict = Depends(auth.current_user),
                  db: Session = Depends(get_db)):
    return {"roadmaps": roadmap_svc.load_all(db, user["uid"])}


@router.post("/roadmaps")
def create_roadmap(body: RoadmapIn,
                   user: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    tf = (body.timeframe or "").strip() or roadmap_svc.parse_timeframe(body.goal)
    rm = roadmap_svc.generate(body.goal, tf, [])
    rid = roadmap_svc.save(db, user["uid"], rm)
    audit_mod.audit(db, action="roadmap_created", actor=user,
                    resource_type="roadmap", resource_id=rid, detail={})
    return roadmap_svc.load_one(db, user["uid"], rid)


@router.get("/roadmaps/{rid}")
def get_roadmap(rid: str, user: dict = Depends(auth.current_user),
                db: Session = Depends(get_db)):
    rm = roadmap_svc.load_one(db, user["uid"], rid)
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    return rm


@router.patch("/roadmaps/{rid}/step/{idx}")
def toggle_roadmap_step(rid: str, idx: int,
                        user: dict = Depends(auth.current_user),
                        db: Session = Depends(get_db)):
    rm = roadmap_svc.toggle_step(db, user["uid"], rid, idx)
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    return rm


class RoadmapStatusIn(BaseModel):
    status: str


@router.patch("/roadmaps/{rid}")
def set_roadmap_status(rid: str, body: RoadmapStatusIn,
                       user: dict = Depends(auth.current_user),
                       db: Session = Depends(get_db)):
    rm = roadmap_svc.set_status(db, user["uid"], rid, body.status)
    if not rm:
        raise HTTPException(400, "Invalid roadmap or status")
    return rm


@router.delete("/roadmaps/{rid}")
def delete_roadmap(rid: str, user: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    if not roadmap_svc.delete(db, user["uid"], rid):
        raise HTTPException(404, "Roadmap not found")
    return {"ok": True}


# ── Safety plan (Stanley-Brown) ──────────────────────────────────────────────
class SafetyPlanIn(BaseModel):
    warning_signs: Optional[list] = None
    coping_strategies: Optional[list] = None
    distractions: Optional[list] = None
    support_people: Optional[list] = None
    safe_environment: Optional[list] = None


@router.get("/safety-plan")
def get_safety_plan(user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    """The user's saved safety plan, or the always-present crisis contacts
    when they haven't made one yet."""
    plan = safety_plan_svc.load(db, user["uid"])
    if plan is None:
        return {"exists": False,
                "professionals": list(safety_plan_svc.CRISIS_CONTACTS)}
    return {"exists": True, **plan}


@router.put("/safety-plan")
def put_safety_plan(body: SafetyPlanIn,
                    user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    """User edits/owns their plan. Crisis contacts are re-attached server-side
    and can't be removed."""
    plan = {k: [str(x).strip()[:200] for x in (v or []) if str(x).strip()]
            for k, v in body.model_dump().items()}
    safety_plan_svc.save(db, user["uid"], plan)
    audit_mod.audit(db, action="safety_plan_saved", actor=user,
                    resource_type="safety_plan", resource_id=user["uid"],
                    detail={})
    return {"ok": True, **(safety_plan_svc.load(db, user["uid"]) or {})}


# ── Preference defaults ──────────────────────────────────────────────────────
DEFAULT_PREFS = {
    "notifications": {
        "screening": True, "lessons": True, "ai_support": True,
        "email": False, "browser_push": True,
    },
    "privacy": {"share_anonymous": True, "ai_remember": True},
    "app": {"language": "en", "theme": "light", "font_size": "medium"},
}
DEFAULT_CONSENT = {"store_data": True, "emails": True, "data_use": True}


def _merge(base: dict, override) -> dict:
    """Deep-merge a stored partial prefs dict over the defaults."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    if isinstance(override, dict):
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = _merge(out[k], v)
            else:
                out[k] = v
    return out


def _dec(b) -> Optional[str]:
    if not b:
        return None
    try:
        return decrypt_str(b)
    except Exception:                                        # noqa: BLE001
        return None


def _enc(s):
    s = (s or "").strip()
    return encrypt_phi(s) if s else None


def _emergency(p: models_admin.UserProfile) -> dict:
    raw = _dec(p.emergency_contact_enc)
    if not raw:
        return {"name": None, "relationship": None, "phone": None}
    try:
        d = json.loads(raw)
        return {"name": d.get("name"), "relationship": d.get("relationship"),
                "phone": d.get("phone")}
    except Exception:                                        # noqa: BLE001
        # legacy plain string
        return {"name": raw, "relationship": None, "phone": None}


def _get_or_create(db: Session, uid) -> models_admin.UserProfile:
    p = db.query(models_admin.UserProfile).filter_by(user_id=uid).first()
    if not p:
        p = models_admin.UserProfile(user_id=uid)
        db.add(p)
        db.flush()
    return p


def _intake_demo(db: Session, uid) -> dict:
    row = (db.query(models.IntakeForm).filter_by(user_id=uid)
           .order_by(models.IntakeForm.created_at.desc()).first())
    return (row.demographics or {}) if row else {}


# ── Request bodies ───────────────────────────────────────────────────────────
class EmergencyIn(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None


class ProfileIn(BaseModel):
    full_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone: Optional[str] = None
    wellness_goal: Optional[str] = None
    emergency: Optional[EmergencyIn] = None


class SettingsIn(BaseModel):
    prefs: Optional[dict] = None
    consent: Optional[dict] = None
    emergency: Optional[EmergencyIn] = None


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


# ── Profile ──────────────────────────────────────────────────────────────────
def _profile_payload(db: Session, u: models.User, p: models_admin.UserProfile) -> dict:
    demo = _intake_demo(db, u.id)
    return {
        "username": u.username,
        "email": u.email or (u.username if "@" in (u.username or "") else None),
        "joined": u.created_at.isoformat() if u.created_at else None,
        "full_name": _dec(p.full_name_enc) or (u.username or "").split("@")[0],
        "gender": p.gender or demo.get("gender"),
        "age": demo.get("age") or demo.get("age_group"),
        "date_of_birth": _dec(p.date_of_birth_enc),
        "phone": _dec(p.phone_enc),
        "wellness_goal": p.wellness_goal,
        "avatar_url": p.avatar_url,
        "emergency": _emergency(p),
        "consent": _merge(DEFAULT_CONSENT, p.consent),
        "consent_updated_at": (p.consent_updated_at.isoformat()
                               if p.consent_updated_at else
                               (u.consent_at.isoformat() if u.consent_at else None)),
    }


@router.get("/profile")
def get_profile(user: dict = Depends(auth.current_user),
                db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if not u:
        raise HTTPException(404, "User not found")
    p = _get_or_create(db, u.id)
    return _profile_payload(db, u, p)


def _apply_emergency(p: models_admin.UserProfile, em: EmergencyIn) -> None:
    cur = _emergency(p)
    if em.name is not None:
        cur["name"] = em.name.strip() or None
    if em.relationship is not None:
        cur["relationship"] = em.relationship.strip() or None
    if em.phone is not None:
        cur["phone"] = em.phone.strip() or None
    p.emergency_contact_enc = (encrypt_phi(json.dumps(cur, ensure_ascii=False))
                               if any(cur.values()) else None)


@router.put("/profile")
def update_profile(body: ProfileIn, request: Request,
                   user: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if not u:
        raise HTTPException(404, "User not found")
    p = _get_or_create(db, u.id)
    if body.full_name is not None:
        p.full_name_enc = _enc(body.full_name)
    if body.gender is not None:
        p.gender = body.gender.strip() or None
    if body.date_of_birth is not None:
        p.date_of_birth_enc = _enc(body.date_of_birth)
    if body.phone is not None:
        p.phone_enc = _enc(body.phone)
    if body.wellness_goal is not None:
        p.wellness_goal = body.wellness_goal.strip() or None
    if body.emergency is not None:
        _apply_emergency(p, body.emergency)
    p.updated_at = datetime.now(timezone.utc)
    audit_mod.audit(db, action="profile_update", actor=user,
                    ip=auth.client_ip(request),
                    resource_type="user", resource_id=u.id, detail={})
    return _profile_payload(db, u, p)


# ── Settings ─────────────────────────────────────────────────────────────────
def _settings_payload(db: Session, u: models.User, p: models_admin.UserProfile) -> dict:
    return {
        "account": {
            "full_name": _dec(p.full_name_enc) or (u.username or "").split("@")[0],
            "email": u.email or (u.username if "@" in (u.username or "") else None),
            "joined": u.created_at.isoformat() if u.created_at else None,
        },
        "prefs": _merge(DEFAULT_PREFS, p.prefs),
        "consent": _merge(DEFAULT_CONSENT, p.consent),
        "emergency": _emergency(p),
    }


@router.get("/settings")
def get_settings(user: dict = Depends(auth.current_user),
                 db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if not u:
        raise HTTPException(404, "User not found")
    p = _get_or_create(db, u.id)
    return _settings_payload(db, u, p)


@router.put("/settings")
def update_settings(body: SettingsIn, request: Request,
                    user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if not u:
        raise HTTPException(404, "User not found")
    p = _get_or_create(db, u.id)
    if body.prefs is not None:
        p.prefs = _merge(_merge(DEFAULT_PREFS, p.prefs), body.prefs)
    if body.consent is not None:
        p.consent = _merge(_merge(DEFAULT_CONSENT, p.consent), body.consent)
        p.consent_updated_at = datetime.now(timezone.utc)
    if body.emergency is not None:
        _apply_emergency(p, body.emergency)
    p.updated_at = datetime.now(timezone.utc)
    return _settings_payload(db, u, p)


@router.post("/password")
def change_password(body: PasswordIn, request: Request,
                    user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if not u:
        raise HTTPException(404, "User not found")
    if not auth.verify_password(body.current_password, u.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password or "") < 6:
        raise HTTPException(400, "New password must be at least 6 characters")
    u.password_hash = auth.hash_password(body.new_password)
    audit_mod.audit(db, action="password_change", actor=user,
                    ip=auth.client_ip(request),
                    resource_type="user", resource_id=u.id, detail={})
    return {"ok": True}


# ── Overview (stats + streak + recent activity) ──────────────────────────────
def _activity_dates(db: Session, uid, since) -> set:
    days = set()
    for created, in (db.query(models.Screening.created_at)
                     .filter(models.Screening.user_id == uid).all()):
        if created and created.date() >= since:
            days.add(created.date())
    for updated, in (db.query(models.UserLessonProgress.updated_at)
                     .filter(models.UserLessonProgress.user_id == uid).all()):
        if updated and updated.date() >= since:
            days.add(updated.date())
    for updated, in (db.query(models.Conversation.updated_at)
                     .filter(models.Conversation.user_id == uid).all()):
        if updated and updated.date() >= since:
            days.add(updated.date())
    return days


@router.get("/overview")
def overview(user: dict = Depends(auth.current_user),
             db: Session = Depends(get_db)):
    uid = user["uid"]
    today = datetime.now(timezone.utc).date()

    screenings = (db.query(models.Screening)
                  .filter_by(user_id=uid)
                  .order_by(models.Screening.created_at.desc()).all())
    last_screening = screenings[0] if screenings else None
    ai_sessions = db.query(models.Conversation).filter_by(user_id=uid).count()
    lessons_completed = (db.query(models.UserLessonProgress)
                         .filter_by(user_id=uid, status="completed").count())
    resources_saved = db.query(models.SavedResource).filter_by(user_id=uid).count()

    # Most-worked-on CBT theme: the technique that shows up most across this
    # user's answered sessions (a light "what you tend to focus on" signal).
    _IGNORE_TECH = {"preference", "(unparsed)", "safety", "greeting", ""}
    techs = [t for (t,) in db.query(models.Session.final_technique)
             .filter(models.Session.user_id == uid,
                     models.Session.final_technique.isnot(None)).all()
             if t and t.strip().lower() not in _IGNORE_TECH]
    top_technique = Counter(techs).most_common(1)[0][0] if techs else None

    # learning/activity streak — consecutive days (ending today or yesterday)
    days = _activity_dates(db, uid, today - timedelta(days=60))
    streak = 0
    cursor = today if today in days else (today - timedelta(days=1))
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    # this week's Mon..Sun activity flags
    monday = today - timedelta(days=today.weekday())
    week = [bool((monday + timedelta(days=i)) in days) for i in range(7)]

    # recent activity feed from real events
    feed = []
    for s in screenings[:5]:
        lvl = s.phq9_level or s.gad7_level or "completed"
        feed.append({"type": "screening", "icon": "shield",
                     "title": "Completed Screening",
                     "detail": f"PHQ-9 {s.phq9_score if s.phq9_score is not None else '-'} · "
                               f"GAD-7 {s.gad7_score if s.gad7_score is not None else '-'} ({lvl})",
                     "time": s.created_at.isoformat() if s.created_at else None})
    done = (db.query(models.UserLessonProgress, models.Lesson)
            .join(models.Lesson, models.Lesson.id == models.UserLessonProgress.lesson_id)
            .filter(models.UserLessonProgress.user_id == uid)
            .order_by(models.UserLessonProgress.updated_at.desc()).limit(5).all())
    for prog, lesson in done:
        feed.append({"type": "lesson", "icon": "book",
                     "title": "Completed Lesson" if prog.status == "completed" else "Lesson Progress",
                     "detail": lesson.title,
                     "time": prog.updated_at.isoformat() if prog.updated_at else None})
    convos = (db.query(models.Conversation).filter_by(user_id=uid)
              .order_by(models.Conversation.updated_at.desc()).limit(5).all())
    for c in convos:
        feed.append({"type": "chat", "icon": "chat",
                     "title": "AI Support Conversation", "detail": c.title,
                     "time": c.updated_at.isoformat() if c.updated_at else None})
    feed = [f for f in feed if f["time"]]
    feed.sort(key=lambda f: f["time"], reverse=True)

    return {
        "screenings_completed": len(screenings),
        "last_screening_at": last_screening.created_at.isoformat() if last_screening and last_screening.created_at else None,
        "ai_sessions": ai_sessions,
        "lessons_completed": lessons_completed,
        "resources_saved": resources_saved,
        "top_technique": top_technique,
        "lessons_done": progress_stats.lessons_done(db, uid),
        "common_themes": progress_stats.common_themes(db, uid),
        "stress_trend": progress_stats.stress_trend(db, uid),
        "streak": streak,
        "week": week,
        "recent_activity": feed[:8],
    }


# ── Saved resources (bookmarks) ──────────────────────────────────────────────
@router.get("/saved-resources")
def saved_resources(user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    rows = (db.query(models.Resource)
            .join(models.SavedResource,
                  models.SavedResource.resource_id == models.Resource.id)
            .filter(models.SavedResource.user_id == user["uid"])
            .order_by(models.SavedResource.created_at.desc()).all())
    return {"resources": [{
        "id": str(r.id), "title": r.title, "type": r.type,
        "category": r.category, "duration": r.duration,
        "urgent": bool(r.urgent) or r.status == "urgent",
    } for r in rows]}


@router.post("/saved-resources/{rid}")
def save_resource(rid: str, user: dict = Depends(auth.current_user),
                  db: Session = Depends(get_db)):
    r = db.query(models.Resource).filter_by(id=rid).first()
    if not r:
        raise HTTPException(404, "Resource not found")
    exists = (db.query(models.SavedResource)
              .filter_by(user_id=user["uid"], resource_id=rid).first())
    if not exists:
        db.add(models.SavedResource(user_id=user["uid"], resource_id=rid))
    return {"ok": True, "saved": True}


@router.delete("/saved-resources/{rid}")
def unsave_resource(rid: str, user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    (db.query(models.SavedResource)
     .filter_by(user_id=user["uid"], resource_id=rid).delete())
    return {"ok": True, "saved": False}


# ── Journal (private by default; opt-in share with clinician) ────────────────
class JournalIn(BaseModel):
    content: str
    mood: Optional[int] = None                 # 1-10
    shared_with_clinician: bool = False


class JournalShareIn(BaseModel):
    shared_with_clinician: bool


def _journal_out(e) -> dict:
    return {
        "id": str(e.id),
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "content": decrypt_str(e.content_enc) or "",
        "mood": e.mood,
        "shared_with_clinician": e.shared_with_clinician,
    }


@router.get("/journal")
def list_journal(user: dict = Depends(auth.current_user),
                 db: Session = Depends(get_db)):
    rows = (db.query(models.JournalEntry)
            .filter_by(user_id=user["uid"])
            .order_by(models.JournalEntry.created_at.desc())
            .limit(100).all())
    return {"entries": [_journal_out(e) for e in rows]}


@router.post("/journal")
def create_journal(body: JournalIn, request: Request,
                   user: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(422, "Journal entry is empty")
    mood = body.mood if body.mood and 1 <= body.mood <= 10 else None
    e = models.JournalEntry(
        user_id=user["uid"], content_enc=encrypt_phi(content[:8000]),
        mood=mood, shared_with_clinician=bool(body.shared_with_clinician))
    db.add(e); db.flush()
    audit_mod.audit(db, action="journal_created", actor=user,
                     ip=auth.client_ip(request),
                     resource_type="journal_entry", resource_id=e.id,
                     detail={"shared": e.shared_with_clinician})
    return _journal_out(e)


@router.patch("/journal/{jid}")
def share_journal(jid: str, body: JournalShareIn, request: Request,
                  user: dict = Depends(auth.current_user),
                  db: Session = Depends(get_db)):
    e = (db.query(models.JournalEntry)
         .filter_by(id=jid, user_id=user["uid"]).first())
    if not e:
        raise HTTPException(404, "Entry not found")
    e.shared_with_clinician = bool(body.shared_with_clinician)
    db.flush()
    audit_mod.audit(db, action="journal_share_toggled", actor=user,
                     ip=auth.client_ip(request),
                     resource_type="journal_entry", resource_id=e.id,
                     detail={"shared": e.shared_with_clinician})
    return _journal_out(e)


@router.delete("/journal/{jid}")
def delete_journal(jid: str, request: Request,
                   user: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    e = (db.query(models.JournalEntry)
         .filter_by(id=jid, user_id=user["uid"]).first())
    if not e:
        raise HTTPException(404, "Entry not found")
    db.delete(e)
    audit_mod.audit(db, action="journal_deleted", actor=user,
                     ip=auth.client_ip(request),
                     resource_type="journal_entry", resource_id=jid)
    return {"ok": True}


# ── Data autonomy: export everything / delete the account ────────────────────
@router.get("/export")
def export_my_data(user: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    """The user's own data as one JSON bundle (their PHI, decrypted for them)."""
    uid = user["uid"]
    u = db.query(models.User).filter_by(id=uid).first()

    convos = (db.query(models.Conversation).filter_by(user_id=uid)
              .order_by(models.Conversation.created_at.asc()).all())
    sessions = (db.query(models.Session).filter_by(user_id=uid)
                .order_by(models.Session.created_at.asc()).all())
    by_convo = {}
    for s in sessions:
        by_convo.setdefault(str(s.conversation_id), []).append({
            "at": s.created_at.isoformat() if s.created_at else None,
            "you": decrypt_str(s.user_input_enc) or "",
            "reply": decrypt_str(s.final_reply_enc) if s.final_reply_enc else "",
            "triage_level": s.triage_level,
        })
    intake = (db.query(models.IntakeForm).filter_by(user_id=uid)
              .order_by(models.IntakeForm.created_at.desc()).first())
    screenings = (db.query(models.Screening).filter_by(user_id=uid)
                  .order_by(models.Screening.created_at.asc()).all())
    journal = (db.query(models.JournalEntry).filter_by(user_id=uid)
               .order_by(models.JournalEntry.created_at.asc()).all())

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {"username": u.username, "email": u.email,
                    "joined": u.created_at.isoformat() if u.created_at else None},
        "intake": (decrypt_str(intake.raw_text_enc) if intake else None),
        "conversations": [{
            "title": c.title,
            "started": c.created_at.isoformat() if c.created_at else None,
            "archived": bool(getattr(c, "archived", False)),
            "messages": by_convo.get(str(c.id), []),
        } for c in convos],
        "screenings": [{
            "at": s.created_at.isoformat() if s.created_at else None,
            "phq9": s.phq9_score, "gad7": s.gad7_score,
            "phq9_level": s.phq9_level, "gad7_level": s.gad7_level,
            "mood": s.mood_score,
        } for s in screenings],
        "journal": [{
            "at": e.created_at.isoformat() if e.created_at else None,
            "content": decrypt_str(e.content_enc) or "",
            "mood": e.mood,
            "shared_with_clinician": e.shared_with_clinician,
        } for e in journal],
        "safety_plan": safety_plan_svc.load(db, uid),
        "roadmaps": roadmap_svc.load_all(db, uid),
    }


class DeleteAccountIn(BaseModel):
    confirm_username: str


@router.delete("/account")
def delete_my_account(body: DeleteAccountIn, request: Request,
                      user: dict = Depends(auth.current_user),
                      db: Session = Depends(get_db)):
    """Hard-delete the account and its personal data. Confirmation = typing the
    exact username. Deletes run in FK-safe order; the audit trail keeps only a
    non-identifying tombstone (actor id, no content)."""
    uid = user["uid"]
    u = db.query(models.User).filter_by(id=uid).first()
    if not u or u.role != "user":
        raise HTTPException(403, "Only user accounts can self-delete")
    if (body.confirm_username or "").strip() != u.username:
        raise HTTPException(422, "Username confirmation does not match")

    audit_mod.audit(db, action="account_deleted", actor=user,
                     ip=auth.client_ip(request),
                     resource_type="user", resource_id=uid, detail={})

    from sqlalchemy import text as _sql
    # 1) session children without ON DELETE CASCADE
    db.execute(_sql("DELETE FROM soap_notes WHERE session_id IN "
                    "(SELECT id FROM sessions WHERE user_id = :u)"), {"u": uid})
    db.execute(_sql("DELETE FROM feedback WHERE user_id = :u OR session_id IN "
                    "(SELECT id FROM sessions WHERE user_id = :u)"), {"u": uid})
    db.execute(_sql("DELETE FROM review_queue WHERE user_id = :u"), {"u": uid})
    # 2) conversations cascade the moderation stack + their sessions + drafts
    db.execute(_sql("DELETE FROM conversations WHERE user_id = :u"), {"u": uid})
    # 3) legacy sessions without a conversation
    db.execute(_sql("DELETE FROM sessions WHERE user_id = :u"), {"u": uid})
    db.execute(_sql("DELETE FROM specialist_assignments WHERE user_id = :u"),
               {"u": uid})
    # 4) the user row — cascades memory/intake/screenings/progress/appointments/
    #    saved resources/journal/profile
    db.execute(_sql("DELETE FROM users WHERE id = :u"), {"u": uid})
    db.flush()
    return {"ok": True, "deleted": True}
