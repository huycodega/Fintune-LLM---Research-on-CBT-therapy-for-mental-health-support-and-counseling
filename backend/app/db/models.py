"""
SQLAlchemy ORM models — matches the v4 Postgres schema.

PHI text columns (user_input, final_reply, intake_raw, drafts.response,
soap_notes.subjective) are stored as BYTEA + AES-256-GCM via
app.core.crypto. Code never reads BYTEA directly — use decrypt_phi().
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, SmallInteger, Boolean, DateTime, LargeBinary,
    ForeignKey, CheckConstraint, Index, JSON, Float, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True,
                         default=uuid.uuid4)


def _now():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# users + RBAC
# ============================================================
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("role IN ('user','clinician','admin')",
                        name="users_role_check"),
    )


# ============================================================
# intake form  (6 sections, parsed)
# ============================================================
class IntakeForm(Base):
    __tablename__ = "intake_forms"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = _now()

    # AES-256-GCM encrypted full original text
    raw_text_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # parsed structured sections
    demographics: Mapped[Optional[dict]] = mapped_column(JSONB)     # §1
    presenting: Mapped[Optional[bytes]] = mapped_column(LargeBinary)  # §2 (PHI)
    reason: Mapped[Optional[str]] = mapped_column(Text)              # §3
    past_history: Mapped[Optional[dict]] = mapped_column(JSONB)      # §4
    functioning: Mapped[Optional[dict]] = mapped_column(JSONB)       # §5
    social_support: Mapped[Optional[str]] = mapped_column(Text)      # §6

    phq9_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gad7_score: Mapped[Optional[int]] = mapped_column(SmallInteger)

    parser_version: Mapped[Optional[str]] = mapped_column(String)
    parse_confidence: Mapped[Optional[float]] = mapped_column(Float)


Index("idx_intake_user", IntakeForm.user_id, IntakeForm.created_at.desc())


# ============================================================
# sessions  (one chat exchange + pipeline outcome)
# ============================================================
class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    intake_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_forms.id"))
    created_at: Mapped[datetime] = _now()
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user_input_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_input_hash: Mapped[str] = mapped_column(String, nullable=False)

    triage_level: Mapped[Optional[str]] = mapped_column(String)   # L0/L1/L2/L3
    triage_reason: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[Optional[float]] = mapped_column(Float)

    analysis: Mapped[Optional[dict]] = mapped_column(JSONB)
    retrieved_ids: Mapped[Optional[list]] = mapped_column(ARRAY(String))
    prompt_hash: Mapped[Optional[str]] = mapped_column(String)

    status: Mapped[str] = mapped_column(String, nullable=False)
    final_reply_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    final_technique: Mapped[Optional[str]] = mapped_column(String)

    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    drafts = relationship("Draft", back_populates="session",
                           cascade="all, delete-orphan", order_by="Draft.idx")

    __table_args__ = (
        CheckConstraint("triage_level IN ('L0','L1','L2','L3')",
                        name="sessions_triage_check"),
        CheckConstraint(
            "status IN ('crisis','pending_review','answered','rejected','auto_sent')",
            name="sessions_status_check"),
    )


Index("idx_sessions_user_time", Session.user_id, Session.created_at.desc())
Index("idx_sessions_pending", Session.status,
      postgresql_where=(Session.status == "pending_review"))
Index("idx_sessions_triage", Session.triage_level, Session.created_at.desc())


# ============================================================
# drafts  (LLM multi-option output)
# ============================================================
class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False)
    idx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    technique: Mapped[Optional[str]] = mapped_column(String)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    plan: Mapped[Optional[str]] = mapped_column(Text)
    response_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    well_formed: Mapped[bool] = mapped_column(Boolean, default=True)
    hallucination_score: Mapped[Optional[float]] = mapped_column(Float)
    preflight_pass: Mapped[Optional[bool]] = mapped_column(Boolean)

    session = relationship("Session", back_populates="drafts")


Index("idx_drafts_session", Draft.session_id, Draft.idx)


# ============================================================
# review queue
# ============================================================
class ReviewQueue(Base):
    __tablename__ = "review_queue"
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"),
        primary_key=True)
    created_at: Mapped[datetime] = _now()
    triage_level: Mapped[Optional[str]] = mapped_column(String)
    priority: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"))
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[Optional[str]] = mapped_column(String)

    __table_args__ = (
        CheckConstraint("resolution IN ('approve','edit','reject')",
                        name="queue_resolution_check"),
    )


Index("idx_queue_open", ReviewQueue.priority, ReviewQueue.sla_due_at,
      postgresql_where=(ReviewQueue.resolved_at.is_(None)))


# ============================================================
# feedback (powers DPO retrain)
# ============================================================
class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    draft_chosen: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id"))
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    edit_diff: Mapped[Optional[dict]] = mapped_column(JSONB)
    clinician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now()


# ============================================================
# SOAP notes
# ============================================================
class SoapNote(Base):
    __tablename__ = "soap_notes"
    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True,
        nullable=False)
    subjective_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    objective: Mapped[Optional[str]] = mapped_column(Text)
    assessment: Mapped[Optional[str]] = mapped_column(Text)
    plan: Mapped[Optional[str]] = mapped_column(Text)
    exported_to_ehr: Mapped[bool] = mapped_column(Boolean, default=False)
    pdf_s3_key: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = _now()


# ============================================================
# audit trail (append-only at DB level via Alembic GRANT)
# ============================================================
class AuditTrail(Base):
    __tablename__ = "audit_trail"
    id: Mapped[uuid.UUID] = _uuid_pk()
    ts: Mapped[datetime] = _now()
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    actor_username: Mapped[Optional[str]] = mapped_column(String)
    actor_role: Mapped[Optional[str]] = mapped_column(String)
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB)


Index("idx_audit_time", AuditTrail.ts.desc())
Index("idx_audit_actor", AuditTrail.actor_id, AuditTrail.ts.desc())
Index("idx_audit_resource", AuditTrail.resource_type, AuditTrail.resource_id)
