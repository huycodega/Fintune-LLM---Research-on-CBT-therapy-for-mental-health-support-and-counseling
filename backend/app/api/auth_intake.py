"""Auth + consent + intake endpoints (user-facing pre-chat flow)."""
import re
import json
import hashlib
import secrets
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.core.config import settings
from app.core.crypto import encrypt_phi
from app.db import models
from app.db.session import get_db
from app.schemas.api import (
    LoginIn, LoginOut, ConsentIn, IntakeIn,
    RegisterIn, VerifyOtpIn, ResendOtpIn, GoogleAuthIn,
)
from app.services import intake_parser, email_sender, redis_client as rc

log = logging.getLogger(__name__)


router = APIRouter(prefix="/api")

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})$")


def _validate_email(email: str) -> str:
    """Normalize + enforce allowed domain (Gmail). Returns lowercased email."""
    email = email.strip().lower()
    m = _EMAIL_RE.match(email)
    if not m:
        raise HTTPException(400, "Invalid email address")
    domain = m.group(1)
    allowed = [d.lower() for d in settings.allowed_email_domains]
    if allowed and domain not in allowed:
        raise HTTPException(
            400, f"Only these email domains are allowed: {', '.join(allowed)}")
    return email


def _gen_otp() -> str:
    n = settings.otp_length
    return "".join(secrets.choice("0123456789") for _ in range(n))


_GOOGLE_ISS = ("accounts.google.com", "https://accounts.google.com")


def _verify_google_token(credential: str) -> dict:
    """Verify a Google Identity Services ID token via Google's tokeninfo
    endpoint and return its claims. Raises 401 on any problem."""
    url = ("https://oauth2.googleapis.com/tokeninfo?id_token="
           + urllib.parse.quote(credential))
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            info = json.loads(r.read().decode())
    except Exception as e:                                    # noqa: BLE001
        log.warning("Google token verification failed: %s", e)
        raise HTTPException(401, "Could not verify Google sign-in")

    if info.get("aud") != settings.google_oauth_client_id:
        raise HTTPException(401, "Google token was issued for a different app")
    if info.get("iss") not in _GOOGLE_ISS:
        raise HTTPException(401, "Invalid Google token issuer")
    return info


# ============================================================
# Gmail self-registration  (step 1: create unverified + email OTP)
# ============================================================
@router.post("/register")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    email = _validate_email(body.email)

    existing = db.query(models.User).filter_by(email=email).first()
    if existing and existing.email_verified:
        raise HTTPException(409, "An account with this email already exists")

    if existing and not existing.email_verified:
        # Re-registration of an unverified account: reset its password and
        # re-send a fresh OTP (lets a user who never verified try again).
        existing.password_hash = auth.hash_password(body.password)
        user = existing
    else:
        user = models.User(
            username=email,                       # Gmail doubles as username
            email=email,
            password_hash=auth.hash_password(body.password),
            role="user",
            email_verified=False,
        )
        db.add(user)
    db.flush()

    code = _gen_otp()
    rc.otp_set(email, code)
    sent = email_sender.send_otp(email, code)

    audit_mod.audit(db, action="register_otp_sent",
                    actor={"uid": str(user.id), "username": email,
                           "role": "user"},
                    ip=auth.client_ip(request),
                    resource_type="user", resource_id=user.id)

    resp = {
        "ok": True,
        "email": email,
        "otp_required": True,
        "delivery": "console" if email_sender.dev_mode() else "email",
        "sent": sent,
    }
    # DEV convenience only: echo the code when no real SMTP is configured.
    if email_sender.dev_mode() and settings.otp_dev_echo:
        resp["dev_otp"] = code
    return resp


# ============================================================
# Gmail self-registration  (step 2: verify OTP → auto-login)
# ============================================================
@router.post("/verify-otp", response_model=LoginOut)
def verify_otp(body: VerifyOtpIn, request: Request,
               db: Session = Depends(get_db)):
    email = _validate_email(body.email)
    user = db.query(models.User).filter_by(email=email).first()
    if not user:
        raise HTTPException(404, "No registration found for this email")
    if user.email_verified:
        raise HTTPException(409, "Email already verified — please log in")

    ok, reason = rc.otp_verify(email, body.otp.strip())
    if not ok:
        msg = {
            "expired": "Code expired — request a new one",
            "mismatch": "Incorrect code",
            "too_many_attempts": "Too many attempts — request a new code",
        }.get(reason, "Verification failed")
        raise HTTPException(400, msg)

    user.email_verified = True
    user.last_login = datetime.now(timezone.utc)
    db.flush()
    audit_mod.audit(db, action="register_verified",
                    actor={"uid": str(user.id), "username": user.username,
                           "role": user.role},
                    ip=auth.client_ip(request),
                    resource_type="user", resource_id=user.id)

    # Auto-login after verification → user proceeds to consent → intake.
    return LoginOut(
        token=auth.make_token(str(user.id), user.username, user.role),
        username=user.username, role=user.role,
        consent_required=(user.consent_at is None),
        intake_required=True,
    )


# ============================================================
# Resend OTP (rate-limited by cooldown)
# ============================================================
@router.post("/resend-otp")
def resend_otp(body: ResendOtpIn, db: Session = Depends(get_db)):
    email = _validate_email(body.email)
    user = db.query(models.User).filter_by(email=email).first()
    if not user:
        raise HTTPException(404, "No registration found for this email")
    if user.email_verified:
        raise HTTPException(409, "Email already verified — please log in")
    if not rc.otp_can_resend(email):
        raise HTTPException(
            429, f"Please wait before requesting another code "
                 f"({settings.otp_resend_cooldown_seconds}s)")

    code = _gen_otp()
    rc.otp_set(email, code)
    sent = email_sender.send_otp(email, code)
    resp = {"ok": True, "sent": sent,
            "delivery": "console" if email_sender.dev_mode() else "email"}
    if email_sender.dev_mode() and settings.otp_dev_echo:
        resp["dev_otp"] = code
    return resp


# ============================================================
# Login (role-scoped — user app sets expected_role=user,
# admin app sets expected_role=admin)
# ============================================================
@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    # Accept either the username/handle or the Gmail address.
    ident = body.username.strip()
    user = (db.query(models.User)
              .filter((models.User.username == ident)
                      | (models.User.email == ident.lower()))
              .first())
    if not user or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    if getattr(user, "status", "active") == "suspended":
        raise HTTPException(
            403, "This account has been suspended. Please contact support.")
    if not user.email_verified:
        raise HTTPException(
            403, "Email not verified — check your inbox for the code")
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


# ============================================================
# Google sign-in (Google Identity Services ID-token flow)
#   The browser obtains a Google ID token; we verify it, then find-or-create
#   the matching user (email already verified by Google) and issue our token.
# ============================================================
@router.post("/auth/google", response_model=LoginOut)
def google_auth(body: GoogleAuthIn, request: Request,
                db: Session = Depends(get_db)):
    if not settings.google_oauth_client_id:
        raise HTTPException(503, "Google sign-in is not configured")

    info = _verify_google_token(body.credential)
    email = (info.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "Google account has no email")
    if str(info.get("email_verified")).lower() != "true":
        raise HTTPException(400, "Google account email is not verified")

    # Keep the same domain policy as Gmail self-registration.
    domain = email.split("@")[-1]
    allowed = [d.lower() for d in settings.allowed_email_domains]
    if allowed and domain not in allowed:
        raise HTTPException(
            400, f"Only these email domains are allowed: {', '.join(allowed)}")

    user = db.query(models.User).filter_by(email=email).first()
    created = False
    if not user:
        # No password is ever used for Google accounts; store a random hash so
        # the NOT NULL column is satisfied and password login can't match.
        user = models.User(
            username=email,
            email=email,
            password_hash=auth.hash_password(secrets.token_urlsafe(32)),
            role="user",
            email_verified=True,
        )
        db.add(user)
        db.flush()
        created = True
    elif not user.email_verified:
        user.email_verified = True

    if getattr(user, "status", "active") == "suspended":
        raise HTTPException(
            403, "This account has been suspended. Please contact support.")
    if body.expected_role and body.expected_role != user.role:
        raise HTTPException(
            403,
            f"Account role '{user.role}' is not allowed on this app "
            f"(expects '{body.expected_role}')")

    user.last_login = datetime.now(timezone.utc)
    db.flush()
    audit_mod.audit(db, action="login_google", actor={
        "uid": str(user.id), "username": user.username, "role": user.role,
    }, ip=auth.client_ip(request), resource_type="user", resource_id=user.id,
        detail={"created": created})

    consent_required = user.role == "user" and user.consent_at is None
    intake_required = False
    if user.role == "user" and not consent_required:
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
