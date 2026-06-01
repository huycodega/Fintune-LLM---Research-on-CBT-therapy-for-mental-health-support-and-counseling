"""Auth + consent + intake endpoints (user-facing pre-chat flow)."""
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.core.crypto import encrypt_phi
from app.db import models
from app.db.session import get_db
from app.schemas.api import LoginIn, LoginOut, ConsentIn, IntakeIn
from app.services import intake_parser


router = APIRouter(prefix="/api")


# ============================================================
# Login (role-scoped — user app sets expected_role=user,
# admin app sets expected_role=admin)
# ============================================================
@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=body.username).first()
    if not user or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    if body.expected_role and body.expected_role != user.role:
        raise HTTPException(
            403,
            f"Account role '{user.role}' is not allowed on this app "
            f"(expects '{body.expected_role}')")
    user.last_login = datetime.now(timezone.utc)
    db.flush()
    audit_mod.audit(db, action="login", actor={
        "uid": str(user.id), "username": user.username, "role": user.role,
    }, ip=auth.client_ip(request))

    consent_required = user.role == "user" and user.consent_at is None
    intake_required = False
    if user.role == "user" and not consent_required:
        # Has the user submitted at least one intake?
        intake_required = (
            db.query(models.IntakeForm)
              .filter_by(user_id=user.id).first() is None
        )
    return LoginOut(
        token=auth.make_token(str(user.id), user.username, user.role),
        username=user.username, role=user.role,
        consent_required=consent_required,
        intake_required=intake_required,
    )


@router.get("/me")
def me(user: dict = Depends(auth.current_user), db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if not u:
        raise HTTPException(404, "User not found")
    needs_consent = u.role == "user" and u.consent_at is None
    needs_intake = False
    if u.role == "user" and not needs_consent:
        needs_intake = (
            db.query(models.IntakeForm).filter_by(user_id=u.id).first()
            is None
        )
    return {
        "username": u.username, "role": u.role,
        "consent_required": needs_consent,
        "intake_required": needs_intake,
    }


# ============================================================
# Consent gate (HIPAA layer 1)
# ============================================================
@router.post("/consent")
def consent(body: ConsentIn, request: Request,
            user: dict = Depends(auth.current_user),
            db: Session = Depends(get_db)):
    if not body.accepted:
        raise HTTPException(400, "Consent must be accepted to use the service")
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    u.consent_at = datetime.now(timezone.utc)
    audit_mod.audit(db, action="consent_accepted", actor=user,
                     ip=auth.client_ip(request),
                     resource_type="user", resource_id=u.id)
    return {"ok": True, "consent_at": u.consent_at.isoformat()}


# ============================================================
# Intake form submission (parsed + 4-route dispatch)
# ============================================================
@router.post("/intake")
def submit_intake(body: IntakeIn, request: Request,
                  user: dict = Depends(auth.current_user),
                  db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if u.consent_at is None:
        raise HTTPException(403, "Consent required before intake")

    parsed = intake_parser.parse_intake(body.raw_text)

    row = models.IntakeForm(
        user_id=u.id,
        raw_text_enc=encrypt_phi(body.raw_text),
        demographics=parsed["demographics"],
        presenting=encrypt_phi(parsed["presenting"]) if parsed["presenting"]
                    else None,
        reason=parsed["reason"],
        past_history=parsed["past_history"],
        functioning=parsed["functioning"],
        social_support=parsed["social_support"],
        parser_version=parsed["parser_version"],
        parse_confidence=parsed["parse_confidence"],
    )
    db.add(row)
    db.flush()

    audit_mod.audit(db, action="intake_submitted", actor=user,
                     ip=auth.client_ip(request),
                     resource_type="intake_form", resource_id=row.id,
                     detail={"parse_confidence": parsed["parse_confidence"]})

    return {
        "intake_id": str(row.id),
        "parse_confidence": parsed["parse_confidence"],
        "sections_recognized": sum(
            1 for k in ("presenting", "reason", "past_history",
                         "functioning", "social_support")
            if parsed.get(k)),
    }


@router.get("/my/intake")
def get_my_intake(user: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    row = (db.query(models.IntakeForm)
             .filter_by(user_id=user["uid"])
             .order_by(models.IntakeForm.created_at.desc())
             .first())
    if not row:
        raise HTTPException(404, "No intake on file")
    return {
        "intake_id": str(row.id),
        "created_at": row.created_at.isoformat(),
        "demographics": row.demographics,
        "reason": row.reason,
        "social_support": row.social_support,
        "parse_confidence": row.parse_confidence,
    }
