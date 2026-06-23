"""
Admin — user management + crisis oversight.

  GET  /api/admin/users              — paginated user list + per-user aggregates
  GET  /api/admin/users/{uid}        — full profile: sessions, screenings,
                                         crisis history, memory, risk
  POST /api/admin/users/{uid}/status — suspend / re-activate an account
  POST /api/admin/users/{uid}/role   — change role (user/clinician/admin)
  GET  /api/admin/crisis             — crisis feed (L0/L1) across all users,
                                         the data admins must control + triage
  GET  /api/admin/overview           — top-line counts for the dashboard

These power the MindCare AI admin console (admin_app). All actions are
audited. PHI message bodies are decrypted only inside detail views, never
in list endpoints.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_

from app.core import auth, audit as audit_mod
from app.core.crypto import decrypt_str
from app.db import models, models_admin
from app.db.session import get_db
from app.schemas.api import UserStatusIn, UserRoleIn
from app.services import admin_principals


router = APIRouter(prefix="/api/admin")


# ─────────────────────────────────────────────────────────────────────────────
# Risk helper — derive a single risk badge from a user's data
# ─────────────────────────────────────────────────────────────────────────────
def _risk_from(current_risk: Optional[str], pending_count: int,
               phq9_level: Optional[str], gad7_level: Optional[str]) -> str:
    """Return only the persisted L0-L3 convention used by the admin UI."""
    if current_risk in ("L0", "L1", "L2", "L3"):
        return current_risk
    severe = {"moderately_severe", "severe"}
    if pending_count > 0 or (phq9_level in severe) or (gad7_level in severe):
        return "L2"
    if phq9_level == "moderate" or gad7_level == "moderate":
        return "L2"
    return "L3"


def _mask_email(email: Optional[str]) -> str:
    if not email or "@" not in email:
        return "-"
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


# ─────────────────────────────────────────────────────────────────────────────
# GET /users — list with aggregates
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/users")
def list_users(
    q: str = Query("", description="search username/email"),
    status: str = Query("", description="active|suspended"),
    risk: str = Query("", description="L0|L1|L2|L3"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: dict = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    # Per-user session aggregates (count, crisis count, pending count, last seen)
    sess_agg = (
        db.query(
            models.Session.user_id.label("uid"),
            func.count(models.Session.id).label("sessions"),
            func.sum(case((models.Session.triage_level.in_(("L0", "L1")), 1),
                          else_=0)).label("crisis"),
            func.sum(case((models.Session.status == "pending_review", 1),
                          else_=0)).label("pending"),
            func.max(models.Session.created_at).label("last_active"),
        )
        .group_by(models.Session.user_id)
        .subquery()
    )

    base = (
        db.query(models.User, sess_agg.c.sessions, sess_agg.c.crisis,
                 sess_agg.c.pending, sess_agg.c.last_active)
        .outerjoin(sess_agg, sess_agg.c.uid == models.User.id)
        .filter(models.User.role == "user")
    )

    if q:
        like = f"%{q.lower()}%"
        base = base.filter(or_(func.lower(models.User.username).like(like),
                               func.lower(models.User.email).like(like)))
    if status in ("active", "suspended"):
        base = base.filter(models.User.status == status)
    if risk in ("L0", "L1", "L2", "L3"):
        base = base.filter(models.User.current_risk_level == risk)

    total = base.count()
    rows = (base.order_by(sess_agg.c.last_active.desc().nullslast(),
                          models.User.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())

    # latest screening level per listed user (one extra query, scoped to page)
    uids = [u.id for (u, *_rest) in rows]
    latest_screen = {}
    if uids:
        sub = (
            db.query(
                models.Screening.user_id,
                func.max(models.Screening.created_at).label("mx"))
            .filter(models.Screening.user_id.in_(uids))
            .group_by(models.Screening.user_id).subquery())
        for sc in (db.query(models.Screening)
                   .join(sub, (sub.c.user_id == models.Screening.user_id) &
                         (sub.c.mx == models.Screening.created_at))
                   .all()):
            latest_screen[sc.user_id] = sc

    assignments = {}
    if uids:
        assigned = (
            db.query(models_admin.SpecialistAssignment, models_admin.AdminUser)
            .join(models_admin.AdminUser,
                  models_admin.AdminUser.id ==
                  models_admin.SpecialistAssignment.clinician_id)
            .filter(models_admin.SpecialistAssignment.user_id.in_(uids),
                    models_admin.SpecialistAssignment.status == "active")
            .all()
        )
        assignments = {
            row.user_id: {"id": str(clin.id), "name": clin.full_name}
            for row, clin in assigned
        }

    out = []
    for (u, sessions, crisis, pending, last_active) in rows:
        sc = latest_screen.get(u.id)
        risk_level = _risk_from(
            u.current_risk_level, int(pending or 0),
            sc.phq9_level if sc else None, sc.gad7_level if sc else None)
        out.append({
            "id": str(u.id),
            "username": u.username,
            "email": _mask_email(u.email),
            "role": u.role,
            "status": u.status,
            "email_verified": u.email_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_active": last_active.isoformat() if last_active else None,
            "sessions": int(sessions or 0),
            "crisis_count": int(crisis or 0),
            "pending_count": int(pending or 0),
            "phq9_level": sc.phq9_level if sc else None,
            "gad7_level": sc.gad7_level if sc else None,
            "mood_score": sc.mood_score if sc else None,
            "risk": risk_level,
            "assigned_clinician": assignments.get(u.id),
        })

    return {"users": out, "total": total, "page": page,
            "page_size": page_size}


# ─────────────────────────────────────────────────────────────────────────────
# GET /users/{uid} — full profile
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/users/{uid}")
def user_detail(uid: str, _: dict = Depends(auth.require_admin),
                db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=uid).first()
    if not u:
        raise HTTPException(404, "User not found")

    sessions = (db.query(models.Session)
                .filter_by(user_id=u.id)
                .order_by(models.Session.created_at.desc()).limit(50).all())
    screenings = (db.query(models.Screening)
                  .filter_by(user_id=u.id)
                  .order_by(models.Screening.created_at.desc()).limit(20).all())
    mem = db.query(models.UserMemory).filter_by(user_id=u.id).first()

    crisis_count = sum(1 for s in sessions if s.triage_level in ("L0", "L1"))
    pending_count = sum(1 for s in sessions if s.status == "pending_review")
    latest = screenings[0] if screenings else None
    assignment = (
        db.query(models_admin.SpecialistAssignment, models_admin.AdminUser)
        .join(models_admin.AdminUser,
              models_admin.AdminUser.id ==
              models_admin.SpecialistAssignment.clinician_id)
        .filter(models_admin.SpecialistAssignment.user_id == u.id,
                models_admin.SpecialistAssignment.status == "active")
        .first()
    )
    clin = assignment[1] if assignment else None

    return {
        "id": str(u.id),
        "username": u.username,
        "email": _mask_email(u.email),
        "role": u.role,
        "status": u.status,
        "assigned_clinician": ({"id": str(clin.id),
                                "name": clin.full_name}
                               if clin else None),
        "email_verified": u.email_verified,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "risk": _risk_from(u.current_risk_level, pending_count,
                           latest.phq9_level if latest else None,
                           latest.gad7_level if latest else None),
        "memory": {
            "summary": mem.summary if mem else None,
            "turn_count": mem.turn_count if mem else 0,
            "updated_at": (mem.updated_at.isoformat()
                           if mem and mem.updated_at else None),
        },
        "sessions": [{
            "id": str(s.id),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "triage_level": s.triage_level,
            "severity": s.severity,
            "status": s.status,
            "preview": (decrypt_str(s.user_input_enc) or "")[:160],
            "final_technique": s.final_technique,
        } for s in sessions],
        "screenings": [{
            "id": str(sc.id),
            "created_at": sc.created_at.isoformat() if sc.created_at else None,
            "phq9_score": sc.phq9_score, "phq9_level": sc.phq9_level,
            "gad7_score": sc.gad7_score, "gad7_level": sc.gad7_level,
            "mood_score": sc.mood_score,
        } for sc in screenings],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /users/{uid}/screening-history — real screening rows for the Screening page
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/users/{uid}/screening-history")
def screening_history(uid: str, _: dict = Depends(auth.require_admin),
                      db: Session = Depends(get_db)):
    rows = (db.query(models.Screening)
            .filter_by(user_id=uid)
            .order_by(models.Screening.created_at.desc()).limit(200).all())
    return {"items": [{
        "id": str(s.id),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "screened_at": s.created_at.isoformat() if s.created_at else None,
        "phq9_score": s.phq9_score,
        "gad7_score": s.gad7_score,
        "phq9_level": s.phq9_level,
        "gad7_level": s.gad7_level,
        "mood_score": s.mood_score,
        "note": s.notes,
        "admin_notes": s.admin_notes or [],
        "status": "completed",
    } for s in rows]}


class ScreeningNoteIn(BaseModel):
    content: str


@router.post("/screenings/{sid}/note")
def add_screening_note(sid: str, body: ScreeningNoteIn, request: Request,
                       actor: dict = Depends(auth.require_admin),
                       db: Session = Depends(get_db)):
    s = db.query(models.Screening).filter_by(id=sid).first()
    if not s:
        raise HTTPException(404, "Screening not found")
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(400, "Note content is required")
    note = {
        "author": actor.get("username") or "clinician",
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # JSONB columns need reassignment for SQLAlchemy to flag the change.
    s.admin_notes = [*(s.admin_notes or []), note]
    audit_mod.audit(db, action="screening_note", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="screening", resource_id=s.id, detail={})
    return {"ok": True, "admin_notes": s.admin_notes}


# ─────────────────────────────────────────────────────────────────────────────
# POST /users/{uid}/status — suspend / activate
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/users/{uid}/status")
def set_user_status(uid: str, body: UserStatusIn, request: Request,
                    actor: dict = Depends(auth.require_admin),
                    db: Session = Depends(get_db)):
    if actor.get("role") != "admin":
        raise HTTPException(403, "Only admins can change account status")
    u = db.query(models.User).filter_by(id=uid).first()
    if not u:
        raise HTTPException(404, "User not found")
    if u.role == "admin":
        raise HTTPException(409, "Cannot change an admin account's status")
    u.status = body.status
    audit_mod.audit(db, action=f"user_{body.status}", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="user", resource_id=u.id,
                    detail={"reason": body.reason})
    return {"ok": True, "id": str(u.id), "status": u.status}


# ─────────────────────────────────────────────────────────────────────────────
# POST /users/{uid}/role — promote / demote
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/users/{uid}/role")
def set_user_role(uid: str, body: UserRoleIn, request: Request,
                  actor: dict = Depends(auth.require_admin),
                  db: Session = Depends(get_db)):
    if actor.get("role") != "admin":
        raise HTTPException(403, "Only admins can change roles")
    u = db.query(models.User).filter_by(id=uid).first()
    if not u:
        raise HTTPException(404, "User not found")
    u.role = body.role
    audit_mod.audit(db, action="user_role_change", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="user", resource_id=u.id,
                    detail={"role": body.role})
    return {"ok": True, "id": str(u.id), "role": u.role}


# ─────────────────────────────────────────────────────────────────────────────
# GET /clinicians — pickable clinicians for assignment
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/clinicians")
def list_clinicians(_: dict = Depends(auth.require_admin),
                    db: Session = Depends(get_db)):
    admin_principals.sync_admin_principals(db)
    rows = (
        db.query(models_admin.AdminUser, models_admin.Role)
        .join(models_admin.Role,
              models_admin.Role.id == models_admin.AdminUser.role_id)
        .filter(models_admin.Role.code.in_(("clinician", "admin")),
                models_admin.AdminUser.status == "active",
                models_admin.AdminUser.deleted_at.is_(None))
        .order_by(models_admin.AdminUser.full_name).all()
    )
    return {"clinicians": [{"id": str(c.id), "name": c.full_name,
                            "role": role.code} for c, role in rows]}


# ─────────────────────────────────────────────────────────────────────────────
# POST /users/{uid}/assign-clinician — set the user's active clinician (§4.4)
# ─────────────────────────────────────────────────────────────────────────────
class AssignClinicianIn(BaseModel):
    clinician_id: str
    note: Optional[str] = ""


@router.post("/users/{uid}/assign-clinician")
def assign_clinician(uid: str, body: AssignClinicianIn, request: Request,
                     actor: dict = Depends(auth.require_admin),
                     db: Session = Depends(get_db)):
    if actor.get("role") != "admin":
        raise HTTPException(403, "Only admins can assign clinicians")
    u = db.query(models.User).filter_by(id=uid).first()
    if not u:
        raise HTTPException(404, "User not found")
    reviewer = admin_principals.ensure_admin_principal(db, actor)
    clin = db.query(models_admin.AdminUser).filter_by(
        id=body.clinician_id, status="active").first()
    if not clin:
        raise HTTPException(400, "clinician_id must be an active clinician/admin")
    clin_role = db.query(models_admin.Role).filter_by(id=clin.role_id).first()
    if not clin_role or clin_role.code not in ("clinician", "admin"):
        raise HTTPException(400, "clinician_id must be an active clinician/admin")
    previous = (db.query(models_admin.SpecialistAssignment)
                .filter_by(user_id=u.id, status="active")
                .with_for_update().all())
    for row in previous:
        admin_principals.end_assignment(row)
    db.add(models_admin.SpecialistAssignment(
        user_id=u.id, clinician_id=clin.id, assigned_by=reviewer.id,
        note=(body.note or "")[:500], status="active"))
    audit_mod.audit(db, action="user_assign_clinician", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="user", resource_id=u.id,
                    detail={"clinician_id": str(clin.id),
                            "note": (body.note or "")[:500]})
    return {"ok": True, "id": str(u.id),
            "assigned_clinician": {"id": str(clin.id),
                                   "name": clin.full_name}}


# ─────────────────────────────────────────────────────────────────────────────
# GET /crisis — crisis feed (L0/L1) admins must control
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/crisis")
def crisis_feed(
    window_days: int = Query(30, ge=1, le=365),
    _: dict = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(models.Session, models.User)
        .join(models.User, models.User.id == models.Session.user_id)
        .filter(models.Session.triage_level.in_(("L0", "L1")))
        .filter(models.Session.created_at >= since)
        .order_by(models.Session.created_at.desc())
        .limit(200).all())

    open_states = {"crisis", "pending_review"}
    out = []
    for s, u in rows:
        out.append({
            "session_id": str(s.id),
            "user_id": str(u.id),
            "username": u.username,
            "triage_level": s.triage_level,
            "severity": s.severity,
            "confidence": s.confidence,
            "status": s.status,
            "resolved": s.status not in open_states,
            "reason": s.triage_reason,
            "preview": (decrypt_str(s.user_input_enc) or "")[:200],
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    counts = {
        "total": len(out),
        "open": sum(1 for r in out if not r["resolved"]),
        "L0": sum(1 for r in out if r["triage_level"] == "L0"),
        "L1": sum(1 for r in out if r["triage_level"] == "L1"),
    }
    return {"crisis": out, "counts": counts, "window_days": window_days}


# ─────────────────────────────────────────────────────────────────────────────
# GET /overview — dashboard top-line
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/overview")
def overview(_: dict = Depends(auth.require_admin),
             db: Session = Depends(get_db)):
    total_users = db.query(func.count(models.User.id)).filter(
        models.User.role == "user").scalar()
    suspended = db.query(func.count(models.User.id)).filter(
        models.User.role == "user", models.User.status == "suspended").scalar()
    active_7d = (db.query(func.count(func.distinct(models.Session.user_id)))
                 .filter(models.Session.created_at >=
                         datetime.now(timezone.utc) - timedelta(days=7))
                 .scalar())
    pending = db.query(func.count(models.ReviewQueue.session_id)).filter(
        models.ReviewQueue.resolved_at.is_(None)).scalar()
    crisis_open = (db.query(func.count(models.Session.id))
                   .filter(models.Session.triage_level.in_(("L0", "L1")))
                   .filter(models.Session.status.in_(
                       ("crisis", "pending_review")))
                   .scalar())
    return {
        "total_users": total_users or 0,
        "suspended_users": suspended or 0,
        "active_7d": active_7d or 0,
        "pending_review": pending or 0,
        "crisis_open": crisis_open or 0,
    }
