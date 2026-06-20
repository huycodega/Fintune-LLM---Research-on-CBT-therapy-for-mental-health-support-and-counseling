"""Per-message persistence helpers for the moderation cutover."""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phi
from app.db import models, models_admin


_RISK_RANK = {"L3": 0, "L2": 1, "L1": 2, "L0": 3}
_PRIORITY = {"L0": 100, "L1": 80, "L2": 50, "L3": 30}
_SLA_MINUTES = {"L0": 5, "L1": 30, "L2": 240, "L3": 360}


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _raise_risk(current: Optional[str], incoming: str) -> str:
    if current not in _RISK_RANK:
        return incoming
    return incoming if _RISK_RANK[incoming] > _RISK_RANK[current] else current


def record_user_message(db: Session, conversation: models.Conversation,
                        user: models.User, content: str,
                        risk_level: str) -> models_admin.AiMessage:
    row = models_admin.AiMessage(
        conversation_id=conversation.id,
        sender="user",
        content_enc=encrypt_phi(content),
        content_hash=content_hash(content),
        risk_level=risk_level,
        moderation_status="not_required",
    )
    db.add(row)
    db.flush()
    conversation.message_count = (conversation.message_count or 0) + 1
    conversation.highest_risk_level = _raise_risk(
        conversation.highest_risk_level, risk_level)
    user.current_risk_level = risk_level
    user.updated_at = datetime.now(timezone.utc)
    return row


def record_ai_message(db: Session, conversation: models.Conversation,
                      parent: models_admin.AiMessage, content: str,
                      risk_level: str, moderation_status: str,
                      confidence: Optional[float] = None,
                      model_name: Optional[str] = None) -> models_admin.AiMessage:
    row = models_admin.AiMessage(
        conversation_id=conversation.id,
        sender="ai",
        parent_message_id=parent.id,
        content_enc=encrypt_phi(content),
        content_hash=content_hash(content),
        risk_level=risk_level,
        ai_confidence=confidence,
        model_name=model_name,
        moderation_status=moderation_status,
    )
    db.add(row)
    db.flush()
    conversation.message_count = (conversation.message_count or 0) + 1
    return row


def enqueue(db: Session, conversation: models.Conversation,
            user_message: models_admin.AiMessage, risk_level: str,
            ai_message: Optional[models_admin.AiMessage] = None,
            kind: Optional[str] = None) -> models_admin.ModerationQueue:
    queue_kind = kind or ("ai_review" if ai_message else "user_escalation")
    if queue_kind == "ai_review" and ai_message is None:
        raise ValueError("ai_review requires an AI message")
    row = models_admin.ModerationQueue(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        ai_message_id=ai_message.id if ai_message else None,
        kind=queue_kind,
        status="pending",
        risk_level=risk_level,
        priority=_PRIORITY[risk_level],
        sla_due_at=(datetime.now(timezone.utc) +
                    timedelta(minutes=_SLA_MINUTES[risk_level])),
    )
    db.add(row)
    db.flush()
    return row
