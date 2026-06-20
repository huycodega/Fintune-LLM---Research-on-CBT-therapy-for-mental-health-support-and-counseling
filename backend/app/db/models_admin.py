"""
SQLAlchemy ORM — User Management & AI Moderation (v2 admin schema).

Reconciled with the running CBT v4 Agent. See
backend/docs/user-management-ai-moderation-database-design.md.

These tables are created by migration 0006_user_mgmt_ai_moderation and are
ADDITIVE — the legacy `sessions`/session-keyed review flow keeps working during
the compatibility window. Encrypted columns (*_enc) hold AES-256-GCM ciphertext
via app.core.crypto; never read BYTEA directly.

Risk convention: DB stores ONLY `risk_level` in {L0,L1,L2,L3}. The agent's
in-memory retrieval routing value ("normal"/"elevated") is `retrieval_tier`,
derived at runtime and NOT persisted. `severity` is likewise derived, not stored.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, SmallInteger, Boolean, DateTime, LargeBinary,
    Numeric, ForeignKey, CheckConstraint, UniqueConstraint, Index, func, text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


_RISK = "risk_level IN ('L0','L1','L2','L3')"


# ============================================================
# RBAC — roles / permissions / admin_users
# ============================================================
class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("code IN ('admin','manager','clinician')",
                        name="roles_code_check"),
    )


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        default="active")
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                     default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','active','suspended','deactivated')",
            name="admin_users_status_check"),
        Index("idx_admin_users_role_status", "role_id", "status",
              postgresql_where=text("deleted_at IS NULL")),
    )


# ============================================================
# user_profiles + specialist_assignments
# ============================================================
class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True)
    full_name_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    phone_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    date_of_birth_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    gender: Mapped[Optional[str]] = mapped_column(String(30))
    address_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    emergency_contact_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    user_group: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class SpecialistAssignment(Base):
    __tablename__ = "specialist_assignments"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        default="active")
    note: Mapped[Optional[str]] = mapped_column(Text)
    assigned_at: Mapped[datetime] = _now()
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('active','ended')",
                        name="specialist_assignments_status_check"),
        Index("uq_specialist_assignment_active_user", "user_id", unique=True,
              postgresql_where=text("status = 'active'")),
    )


# ============================================================
# AI Moderation — ai_messages / review_queue / reviews / revisions
# ============================================================
class AiMessage(Base):
    __tablename__ = "ai_messages"
    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False)
    sender: Mapped[str] = mapped_column(String(10), nullable=False)
    parent_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_messages.id"))
    content_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[Optional[str]] = mapped_column(String(2))
    ai_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    model_name: Mapped[Optional[str]] = mapped_column(String(100))
    moderation_status: Mapped[str] = mapped_column(String(25), nullable=False,
                                                   default="not_required")
    created_at: Mapped[datetime] = _now()
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("sender IN ('user','ai','system')",
                        name="ai_messages_sender_check"),
        CheckConstraint(_RISK + " OR risk_level IS NULL",
                        name="ai_messages_risk_check"),
        CheckConstraint("ai_confidence IS NULL OR "
                        "(ai_confidence >= 0 AND ai_confidence <= 1)",
                        name="ai_messages_confidence_check"),
        CheckConstraint(
            "moderation_status IN ('not_required','pending','approved',"
            "'edited','rejected','need_improvement')",
            name="ai_messages_moderation_status_check"),
        Index("idx_ai_messages_conv_time", "conversation_id", "created_at",
              postgresql_where=text("deleted_at IS NULL")),
        Index("idx_ai_messages_moderation_filter",
              "moderation_status", "risk_level", "created_at",
              postgresql_where=text("deleted_at IS NULL")),
    )


# [RECONCILE #6] The legacy `review_queue` (models.py) is session-keyed: its PK
# is `session_id` with no surrogate id, so it cannot be cleanly extended to a
# per-message queue, and renaming/repurposing it would break the running
# backend. The per-AI-message queue is therefore a NEW table `moderation_queue`;
# legacy `review_queue` is deprecated and dropped at cutover.
class ModerationQueue(Base):
    """Per-AI-message review queue. `ai_message_id` is nullable: L0/L1 turns
    produce NO AI reply, so they queue as kind='user_escalation' anchored on the
    user message instead."""
    __tablename__ = "moderation_queue"
    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False)
    user_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_messages.id"), nullable=False)
    ai_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_messages.id"), unique=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False,
                                      default="ai_review")
    status: Mapped[str] = mapped_column(String(25), nullable=False,
                                        default="pending")
    risk_level: Mapped[str] = mapped_column(String(2), nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"))
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claim_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[Optional[str]] = mapped_column(String(25))
    created_at: Mapped[datetime] = _now()
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        CheckConstraint("kind IN ('ai_review','user_escalation')",
                        name="moderation_queue_kind_check"),
        CheckConstraint("kind = 'user_escalation' OR ai_message_id IS NOT NULL",
                        name="moderation_queue_ai_message_required_check"),
        CheckConstraint(
            "status IN ('pending','claimed','need_improvement','resolved','cancelled')",
            name="moderation_queue_status_check"),
        CheckConstraint(_RISK, name="moderation_queue_risk_check"),
        CheckConstraint("priority >= 0 AND priority <= 100",
                        name="moderation_queue_priority_check"),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('approve','edit','reject')",
            name="moderation_queue_resolution_check"),
        Index("idx_moderation_queue_open_priority",
              "priority", "sla_due_at", "created_at",
              postgresql_where=text("resolved_at IS NULL")),
        Index("idx_moderation_queue_claimant", "claimed_by", "claim_expires_at",
              postgresql_where=text("resolved_at IS NULL")),
    )


class ModerationReview(Base):
    __tablename__ = "moderation_reviews"
    id: Mapped[uuid.UUID] = _uuid_pk()
    queue_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("moderation_queue.id", ondelete="CASCADE"),
        nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False)
    ai_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_messages.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(25), nullable=False)
    empathy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    no_diagnosis: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cbt_based: Mapped[bool] = mapped_column(Boolean, nullable=False)
    safe_response: Mapped[bool] = mapped_column(Boolean, nullable=False)
    referral_when_needed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    no_medication_advice: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                       default=True)
    no_overclaiming: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                  default=True)
    note_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    response_revision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_response_revisions.id"))
    created_at: Mapped[datetime] = _now()
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approve','edit','reject','need_improvement')",
            name="moderation_reviews_decision_check"),
        CheckConstraint(
            "decision NOT IN ('approve','edit') OR "
            "(empathy AND no_diagnosis AND cbt_based AND safe_response "
            "AND referral_when_needed AND no_medication_advice AND no_overclaiming)",
            name="moderation_reviews_checklist_check"),
        Index("idx_moderation_reviews_queue_time", "queue_item_id", "created_at"),
        Index("idx_moderation_reviews_reviewer_time", "reviewer_id", "created_at"),
    )


class AiResponseRevision(Base):
    __tablename__ = "ai_response_revisions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False)
    ai_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_messages.id", ondelete="CASCADE"),
        nullable=False)
    source_draft_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id"))
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    response_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    response_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    edited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    edit_reason_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = _now()
    __table_args__ = (
        UniqueConstraint("ai_message_id", "revision_no",
                         name="uq_ai_response_revision_no"),
    )
