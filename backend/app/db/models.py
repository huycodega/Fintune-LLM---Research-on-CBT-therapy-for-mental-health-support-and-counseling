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
    # Gmail self-registration: account exists but cannot log in until the
    # emailed OTP is confirmed. Seed/clinician accounts are created verified.
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                 default=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    # Account lifecycle, managed by admins: active | suspended.
    # Suspended accounts cannot log in; their data stays for clinical review.
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Additive user-management fields introduced by migration 0006.
    email_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    email_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    current_risk_level: Mapped[Optional[str]] = mapped_column(String(2))
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("role IN ('user','clinician','admin')",
                        name="users_role_check"),
        CheckConstraint("status IN ('active','suspended')",
                        name="users_status_check"),
    )


# ============================================================
# conversations  (a "tasktab" thread grouping many chat turns)
# ============================================================
class Conversation(Base):
    """A multi-turn chat thread. Each turn is a Session (which carries the
    full safety/triage pipeline outcome), linked back via conversation_id.
    The user's sidebar ("tasktab") lists these threads newest-first."""
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False,
                                       default="New conversation")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                           default=False)
    highest_risk_level: Mapped[Optional[str]] = mapped_column(String(2))
    message_count: Mapped[int] = mapped_column(Integer, nullable=False,
                                                default=0)


Index("idx_conversations_user", Conversation.user_id,
      Conversation.updated_at.desc())


# ============================================================
# per-user memory  (durable facts the assistant should remember)
# ============================================================
class UserMemory(Base):
    """One row per user. Accumulates compact, non-PHI-light facts the
    assistant carries across conversations (recurring concerns, what
    techniques helped, preferences). Updated best-effort after each turn.
    `facts` is encrypted (may contain personal context)."""
    __tablename__ = "user_memory"
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    facts_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    summary: Mapped[Optional[str]] = mapped_column(Text)   # short non-PHI gist
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


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
    # Multi-turn thread this exchange belongs to (nullable for legacy rows).
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"))
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
Index("idx_sessions_conversation", Session.conversation_id,
      Session.created_at.asc())
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
    source_user_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_messages.id"))

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


# ============================================================
# screening results  (periodic PHQ-9 / GAD-7 check-ins)
# ============================================================
class Screening(Base):
    """Stores periodic mental health screening results per user.
    Users can complete PHQ-9 / GAD-7 questionnaires multiple times
    to track progress over time."""
    __tablename__ = "screenings"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = _now()

    # PHQ-9 (0-27): depression severity
    phq9_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    phq9_answers: Mapped[Optional[list]] = mapped_column(JSONB)  # [0-3] x 9

    # GAD-7 (0-21): anxiety severity
    gad7_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gad7_answers: Mapped[Optional[list]] = mapped_column(JSONB)  # [0-3] x 7

    # Subjective mood (1-10)
    mood_score: Mapped[Optional[int]] = mapped_column(SmallInteger)

    # Derived level: normal | mild | moderate | moderately_severe | severe
    phq9_level: Mapped[Optional[str]] = mapped_column(String)
    gad7_level: Mapped[Optional[str]] = mapped_column(String)

    notes: Mapped[Optional[str]] = mapped_column(Text)


Index("idx_screenings_user", Screening.user_id, Screening.created_at.desc())


# ============================================================
# learning content  (public CBT lessons — admin-managed, user-facing)
# ============================================================
class Lesson(Base):
    """A CBT micro-lesson shown to users in the Lessons (BaiHoc) page and
    managed by admins in LessonsAdmin. NOT PHI — public educational content,
    so columns are plain text (no encryption)."""
    __tablename__ = "lessons"
    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String)
    # basic | intermediate | advanced
    level: Mapped[str] = mapped_column(String, nullable=False, default="basic")
    duration: Mapped[Optional[str]] = mapped_column(String)   # e.g. "15 min"
    content: Mapped[Optional[str]] = mapped_column(Text)       # lesson body
    objectives: Mapped[Optional[list]] = mapped_column(JSONB)  # ["...", ...]
    tags: Mapped[Optional[list]] = mapped_column(JSONB)        # ["stress", ...]
    # draft | published
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    author: Mapped[Optional[str]] = mapped_column(String)      # display name
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("level IN ('basic','intermediate','advanced')",
                        name="lessons_level_check"),
        CheckConstraint("status IN ('draft','published')",
                        name="lessons_status_check"),
    )


Index("idx_lessons_status", Lesson.status, Lesson.created_at.desc())


# ============================================================
# support resources  (audio / article / video / CBT tool)
# ============================================================
class Resource(Base):
    """A support resource (audio, article, video, CBT tool) shown to users in
    the Resources (TaiNguyen) page and managed by admins in ResourcesAdmin.
    NOT PHI — public content."""
    __tablename__ = "resources"
    id: Mapped[uuid.UUID] = _uuid_pk()
    # Audio | Article | Video | CBT Tool
    type: Mapped[str] = mapped_column(String, nullable=False, default="Article")
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String)
    duration: Mapped[Optional[str]] = mapped_column(String)   # "05:23" or ""
    url: Mapped[Optional[str]] = mapped_column(String)        # external link
    content: Mapped[Optional[str]] = mapped_column(Text)      # inline body
    # published | urgent | update
    status: Mapped[str] = mapped_column(String, nullable=False,
                                        default="published")
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner: Mapped[Optional[str]] = mapped_column(String)      # display name
    tags: Mapped[Optional[list]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "type IN ('Audio','Article','Video','CBT Tool')",
            name="resources_type_check"),
        CheckConstraint(
            "status IN ('published','urgent','update','draft')",
            name="resources_status_check"),
    )


Index("idx_resources_status", Resource.status, Resource.created_at.desc())
Index("idx_resources_type", Resource.type)
