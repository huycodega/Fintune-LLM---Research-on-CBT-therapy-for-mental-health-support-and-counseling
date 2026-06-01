"""Audit trail — append-only HIPAA log helper."""
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.db import models


def audit(db: Session, *, action: str,
          actor: Optional[dict] = None,
          resource_type: Optional[str] = None,
          resource_id: Optional[uuid.UUID] = None,
          ip: Optional[str] = None,
          user_agent: Optional[str] = None,
          detail: Optional[dict] = None) -> None:
    row = models.AuditTrail(
        actor_id=uuid.UUID(actor["uid"]) if actor and "uid" in actor else None,
        actor_username=actor["username"] if actor else None,
        actor_role=actor["role"] if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip,
        user_agent=user_agent,
        detail=detail,
    )
    db.add(row)
