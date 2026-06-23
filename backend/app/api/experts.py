"""
Expert consultation booking.

Public (logged-in users):
  GET    /api/experts                       list active psychologists
  GET    /api/experts/{id}/availability     booked (date, slot) for next 3 weeks
  POST   /api/appointments                  book a slot (status=pending)
  GET    /api/my/appointments               my bookings
  PATCH  /api/my/appointments/{id}          change date/slot (only while pending)
  DELETE /api/my/appointments/{id}          cancel (only while pending)

Admin:
  GET    /api/admin/psychologists           list all (incl. inactive)
  POST   /api/admin/psychologists           create
  PATCH  /api/admin/psychologists/{id}      update
  DELETE /api/admin/psychologists/{id}      delete
  GET    /api/admin/appointments            all bookings (with user + expert)
  PATCH  /api/admin/appointments/{id}       set status (accept / cancel / decline)
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core import auth
from app.db import models
from app.db.session import get_db
from app.schemas.api import (
    PsychologistIn, PsychologistUpdateIn, AppointmentIn, AppointmentUpdateIn,
    AppointmentStatusIn,
)

router = APIRouter(prefix="/api")

BOOKING_WINDOW_DAYS = 21          # can't book more than 3 weeks out
_ACTIVE = ("pending", "accepted")  # statuses that occupy a slot
_DEFAULT_SLOTS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]


# ── serializers ──────────────────────────────────────────────────────────────
def _expert_out(p: models.Psychologist) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "phone": p.phone or "",
        "experience": p.experience or "",
        "specialty": p.specialty or "",
        "bio": p.bio or "",
        "slots": p.slots or _DEFAULT_SLOTS,
        "active": p.active,
    }


def _appt_out(a: models.Appointment, expert=None) -> dict:
    out = {
        "id": str(a.id),
        "psychologist_id": str(a.psychologist_id),
        "date": a.date.isoformat() if a.date else None,
        "slot": a.slot,
        "status": a.status,
        "note": a.note or "",
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
    if expert is not None:
        out["psychologist"] = {
            "id": str(expert.id), "name": expert.name,
            "phone": expert.phone or "", "specialty": expert.specialty or "",
        }
    return out


def _get_expert(db, eid):
    p = db.query(models.Psychologist).filter_by(id=eid).first()
    if not p:
        raise HTTPException(404, "Psychologist not found")
    return p


def _within_window(d: date):
    today = date.today()
    if d < today:
        raise HTTPException(400, "Cannot book a date in the past")
    if d > today + timedelta(days=BOOKING_WINDOW_DAYS):
        raise HTTPException(400, "Cannot book more than 3 weeks ahead")


def _slot_taken(db, expert_id, d, slot, exclude_id=None) -> bool:
    q = (db.query(models.Appointment)
           .filter(models.Appointment.psychologist_id == expert_id,
                   models.Appointment.date == d,
                   models.Appointment.slot == slot,
                   models.Appointment.status.in_(_ACTIVE)))
    if exclude_id:
        q = q.filter(models.Appointment.id != exclude_id)
    return db.query(q.exists()).scalar()


# ── public: experts + availability ───────────────────────────────────────────
@router.get("/experts")
def list_experts(_: dict = Depends(auth.current_user),
                 db: Session = Depends(get_db)):
    rows = (db.query(models.Psychologist).filter_by(active=True)
              .order_by(models.Psychologist.name).all())
    return {"experts": [_expert_out(p) for p in rows]}


@router.get("/experts/{eid}/availability")
def expert_availability(eid: str, _: dict = Depends(auth.current_user),
                        db: Session = Depends(get_db)):
    p = _get_expert(db, eid)
    today = date.today()
    end = today + timedelta(days=BOOKING_WINDOW_DAYS)
    rows = (db.query(models.Appointment)
              .filter(models.Appointment.psychologist_id == eid,
                      models.Appointment.date >= today,
                      models.Appointment.date <= end,
                      models.Appointment.status.in_(_ACTIVE)).all())
    booked = [{"date": a.date.isoformat(), "slot": a.slot} for a in rows]
    return {
        "expert": _expert_out(p),
        "window": {"from": today.isoformat(), "to": end.isoformat(),
                   "days": BOOKING_WINDOW_DAYS},
        "booked": booked,
    }


# ── public: appointments ─────────────────────────────────────────────────────
@router.post("/appointments")
def book_appointment(body: AppointmentIn, user: dict = Depends(auth.current_user),
                     db: Session = Depends(get_db)):
    p = _get_expert(db, body.psychologist_id)
    if not p.active:
        raise HTTPException(400, "This psychologist is not available")
    _within_window(body.date)
    slots = p.slots or _DEFAULT_SLOTS
    if body.slot not in slots:
        raise HTTPException(400, "That time slot isn't offered")
    if _slot_taken(db, p.id, body.date, body.slot):
        raise HTTPException(409, "That slot was just taken — pick another")
    appt = models.Appointment(
        user_id=user["uid"], psychologist_id=p.id,
        date=body.date, slot=body.slot, status="pending",
        note=(body.note or "").strip()[:500])
    db.add(appt); db.flush()
    return _appt_out(appt, p)


@router.get("/my/appointments")
def my_appointments(user: dict = Depends(auth.current_user),
                    db: Session = Depends(get_db)):
    rows = (db.query(models.Appointment)
              .filter_by(user_id=user["uid"])
              .order_by(models.Appointment.created_at.desc()).all())
    experts = {p.id: p for p in db.query(models.Psychologist).all()}
    return {"appointments": [
        _appt_out(a, experts.get(a.psychologist_id)) for a in rows]}


@router.patch("/my/appointments/{aid}")
def change_appointment(aid: str, body: AppointmentUpdateIn,
                       user: dict = Depends(auth.current_user),
                       db: Session = Depends(get_db)):
    a = db.query(models.Appointment).filter_by(id=aid).first()
    if not a or str(a.user_id) != user["uid"]:
        raise HTTPException(404, "Appointment not found")
    if a.status != "pending":
        raise HTTPException(409, "Only pending appointments can be changed")
    new_date = body.date or a.date
    new_slot = body.slot or a.slot
    _within_window(new_date)
    p = _get_expert(db, a.psychologist_id)
    if new_slot not in (p.slots or _DEFAULT_SLOTS):
        raise HTTPException(400, "That time slot isn't offered")
    if _slot_taken(db, a.psychologist_id, new_date, new_slot, exclude_id=a.id):
        raise HTTPException(409, "That slot is already booked")
    a.date = new_date
    a.slot = new_slot
    db.flush()
    return _appt_out(a, p)


@router.delete("/my/appointments/{aid}")
def cancel_appointment(aid: str, user: dict = Depends(auth.current_user),
                       db: Session = Depends(get_db)):
    a = db.query(models.Appointment).filter_by(id=aid).first()
    if not a or str(a.user_id) != user["uid"]:
        raise HTTPException(404, "Appointment not found")
    if a.status != "pending":
        raise HTTPException(409, "Only pending appointments can be cancelled")
    a.status = "cancelled"
    db.flush()
    return {"ok": True, "id": aid, "status": "cancelled"}


# ── admin: psychologists CRUD ────────────────────────────────────────────────
@router.get("/admin/psychologists")
def admin_list_experts(_: dict = Depends(auth.require_admin),
                       db: Session = Depends(get_db)):
    rows = (db.query(models.Psychologist)
              .order_by(models.Psychologist.created_at.desc()).all())
    return {"experts": [_expert_out(p) for p in rows]}


@router.post("/admin/psychologists")
def admin_create_expert(body: PsychologistIn,
                        _: dict = Depends(auth.require_admin),
                        db: Session = Depends(get_db)):
    p = models.Psychologist(
        name=body.name.strip(), phone=body.phone.strip(),
        experience=body.experience.strip(), specialty=body.specialty.strip(),
        bio=body.bio.strip(), slots=body.slots or _DEFAULT_SLOTS,
        active=body.active)
    db.add(p); db.flush()
    return _expert_out(p)


@router.patch("/admin/psychologists/{eid}")
def admin_update_expert(eid: str, body: PsychologistUpdateIn,
                        _: dict = Depends(auth.require_admin),
                        db: Session = Depends(get_db)):
    p = _get_expert(db, eid)
    for field in ("name", "phone", "experience", "specialty", "bio",
                  "slots", "active"):
        val = getattr(body, field)
        if val is not None:
            setattr(p, field, val)
    db.flush()
    return _expert_out(p)


@router.delete("/admin/psychologists/{eid}")
def admin_delete_expert(eid: str, _: dict = Depends(auth.require_admin),
                        db: Session = Depends(get_db)):
    p = _get_expert(db, eid)
    db.delete(p)
    return {"ok": True, "id": eid}


# ── admin: appointments ──────────────────────────────────────────────────────
@router.get("/admin/appointments")
def admin_list_appointments(expert_id: str = Query(""),
                            _: dict = Depends(auth.require_admin),
                            db: Session = Depends(get_db)):
    q = db.query(models.Appointment)
    if expert_id:
        q = q.filter(models.Appointment.psychologist_id == expert_id)
    rows = q.order_by(models.Appointment.created_at.desc()).all()
    experts = {p.id: p for p in db.query(models.Psychologist).all()}
    users = {u.id: u for u in db.query(models.User).all()}
    out = []
    for a in rows:
        d = _appt_out(a, experts.get(a.psychologist_id))
        u = users.get(a.user_id)
        d["user"] = {"name": (u.username.split("@")[0] if u else "User")}
        out.append(d)
    return {"appointments": out}


@router.patch("/admin/appointments/{aid}")
def admin_set_appointment_status(aid: str, body: AppointmentStatusIn,
                                 _: dict = Depends(auth.require_admin),
                                 db: Session = Depends(get_db)):
    a = db.query(models.Appointment).filter_by(id=aid).first()
    if not a:
        raise HTTPException(404, "Appointment not found")
    a.status = body.status
    db.flush()
    return {"ok": True, "id": aid, "status": a.status}
