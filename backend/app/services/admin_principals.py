"""Bridge legacy staff accounts into the v2 admin RBAC schema."""
import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phi
from app.db import models, models_admin


def ensure_admin_principal(db: Session, actor: dict) -> models_admin.AdminUser:
    """Return the AdminUser represented by a legacy staff JWT.

    The compatibility window still authenticates against ``users``. Staff IDs
    are preserved in ``admin_users`` so audit/reviewer foreign keys remain
    stable when authentication is cut over later.
    """
    existing = db.query(models_admin.AdminUser).filter_by(id=actor["uid"]).first()
    if existing:
        return existing

    legacy = db.query(models.User).filter_by(id=actor["uid"]).first()
    if not legacy or legacy.role not in ("admin", "clinician"):
        raise ValueError("Staff principal is missing or inactive")
    role = db.query(models_admin.Role).filter_by(code=legacy.role).first()
    if not role:
        raise ValueError("RBAC roles are not seeded; run alembic upgrade head")

    email = (legacy.email or
             (legacy.username if "@" in legacy.username
              else f"{legacy.username}@local.invalid")).lower()
    row = models_admin.AdminUser(
        id=legacy.id,
        username=legacy.username[:80],
        full_name=legacy.username.split("@")[0][:150],
        email_enc=encrypt_phi(email),
        email_hash=hashlib.sha256(email.encode("utf-8")).hexdigest(),
        password_hash=legacy.password_hash,
        role_id=role.id,
        status="active" if legacy.status == "active" else "suspended",
        last_login_at=legacy.last_login,
    )
    db.add(row)
    db.flush()
    return row


def sync_admin_principals(db: Session) -> int:
    """Idempotently mirror all active legacy staff accounts."""
    count = 0
    staff = db.query(models.User).filter(
        models.User.role.in_(("admin", "clinician"))).all()
    for user in staff:
        ensure_admin_principal(db, {
            "uid": str(user.id), "username": user.username, "role": user.role,
        })
        count += 1
    return count


def end_assignment(row: models_admin.SpecialistAssignment) -> None:
    row.status = "ended"
    row.ended_at = datetime.now(timezone.utc)
