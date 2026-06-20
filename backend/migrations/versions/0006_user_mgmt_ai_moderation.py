"""User Management & AI Moderation v2 — RBAC, ai_messages, per-message queue

Reconciled with the running CBT v4 Agent. Additive & non-breaking: creates new
tables and adds nullable columns; the legacy sessions/review_queue flow keeps
working during the compatibility window (see
backend/docs/user-management-ai-moderation-database-design.md, section 9).

Revision ID: 0006_user_mgmt_ai_moderation
Revises: 0005_lessons_resources
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006_user_mgmt_ai_moderation"
down_revision = "0005_lessons_resources"
branch_labels = None
depends_on = None

_RISK = "risk_level IN ('L0','L1','L2','L3')"


def upgrade():
    # ---- RBAC ----------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text()),
        sa.CheckConstraint("code IN ('admin','manager','clinician')",
                           name="roles_code_check"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID(as_uuid=True),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", UUID(as_uuid=True),
                  sa.ForeignKey("permissions.id", ondelete="CASCADE"),
                  primary_key=True),
    )
    op.create_table(
        "admin_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email_enc", sa.LargeBinary(), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role_id", UUID(as_uuid=True),
                  sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="active"),
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending','active','suspended','deactivated')",
            name="admin_users_status_check"),
    )
    op.create_index("idx_admin_users_role_status", "admin_users",
                    ["role_id", "status"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ---- user profile + specialist assignment --------------------------------
    op.create_table(
        "user_profiles",
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("full_name_enc", sa.LargeBinary()),
        sa.Column("phone_enc", sa.LargeBinary()),
        sa.Column("date_of_birth_enc", sa.LargeBinary()),
        sa.Column("gender", sa.String(30)),
        sa.Column("address_enc", sa.LargeBinary()),
        sa.Column("emergency_contact_enc", sa.LargeBinary()),
        sa.Column("user_group", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )

    # ---- ai_messages (multi-turn) --------------------------------------------
    op.create_table(
        "ai_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("sender", sa.String(10), nullable=False),
        sa.Column("parent_message_id", UUID(as_uuid=True),
                  sa.ForeignKey("ai_messages.id")),
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("risk_level", sa.String(2)),
        sa.Column("ai_confidence", sa.Numeric(5, 4)),
        sa.Column("model_name", sa.String(100)),
        sa.Column("moderation_status", sa.String(25), nullable=False,
                  server_default="not_required"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("sender IN ('user','ai','system')",
                           name="ai_messages_sender_check"),
        sa.CheckConstraint(_RISK + " OR risk_level IS NULL",
                           name="ai_messages_risk_check"),
        sa.CheckConstraint(
            "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)",
            name="ai_messages_confidence_check"),
        sa.CheckConstraint(
            "moderation_status IN ('not_required','pending','approved',"
            "'edited','rejected','need_improvement')",
            name="ai_messages_moderation_status_check"),
    )
    op.create_index("idx_ai_messages_conv_time", "ai_messages",
                    ["conversation_id", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_ai_messages_moderation_filter", "ai_messages",
                    ["moderation_status", "risk_level", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "specialist_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("clinician_id", UUID(as_uuid=True),
                  sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("assigned_by", UUID(as_uuid=True),
                  sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="active"),
        sa.Column("note", sa.Text()),
        sa.Column("assigned_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active','ended')",
                           name="specialist_assignments_status_check"),
    )
    op.create_index("uq_specialist_assignment_active_user",
                    "specialist_assignments", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))

    # ---- ai_response_revisions (before moderation_reviews FK) ----------------
    op.create_table(
        "ai_response_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("ai_message_id", UUID(as_uuid=True),
                  sa.ForeignKey("ai_messages.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_draft_id", UUID(as_uuid=True),
                  sa.ForeignKey("drafts.id")),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("response_enc", sa.LargeBinary(), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("edited_by", UUID(as_uuid=True),
                  sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("edit_reason_enc", sa.LargeBinary()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.UniqueConstraint("ai_message_id", "revision_no",
                            name="uq_ai_response_revision_no"),
    )

    # ---- moderation_queue (per-message; ai_message_id nullable for L0/L1) -----
    op.create_table(
        "moderation_queue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("user_message_id", UUID(as_uuid=True),
                  sa.ForeignKey("ai_messages.id"), nullable=False),
        sa.Column("ai_message_id", UUID(as_uuid=True),
                  sa.ForeignKey("ai_messages.id"), unique=True),
        sa.Column("kind", sa.String(20), nullable=False,
                  server_default="ai_review"),
        sa.Column("status", sa.String(25), nullable=False,
                  server_default="pending"),
        sa.Column("risk_level", sa.String(2), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False,
                  server_default="0"),
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_by", UUID(as_uuid=True),
                  sa.ForeignKey("admin_users.id")),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True)),
        sa.Column("resolution", sa.String(25)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("kind IN ('ai_review','user_escalation')",
                           name="moderation_queue_kind_check"),
        sa.CheckConstraint(
            "kind = 'user_escalation' OR ai_message_id IS NOT NULL",
            name="moderation_queue_ai_message_required_check"),
        sa.CheckConstraint(
            "status IN ('pending','claimed','need_improvement','resolved','cancelled')",
            name="moderation_queue_status_check"),
        sa.CheckConstraint(_RISK, name="moderation_queue_risk_check"),
        sa.CheckConstraint("priority >= 0 AND priority <= 100",
                           name="moderation_queue_priority_check"),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('approve','edit','reject')",
            name="moderation_queue_resolution_check"),
    )
    op.create_index("idx_moderation_queue_open_priority", "moderation_queue",
                    ["priority", "sla_due_at", "created_at"],
                    postgresql_where=sa.text("resolved_at IS NULL"))
    op.create_index("idx_moderation_queue_claimant", "moderation_queue",
                    ["claimed_by", "claim_expires_at"],
                    postgresql_where=sa.text("resolved_at IS NULL"))

    # ---- moderation_reviews (immutable checklist + decision) -----------------
    op.create_table(
        "moderation_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("moderation_queue.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("ai_message_id", UUID(as_uuid=True),
                  sa.ForeignKey("ai_messages.id")),
        sa.Column("reviewer_id", UUID(as_uuid=True),
                  sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("decision", sa.String(25), nullable=False),
        sa.Column("empathy", sa.Boolean(), nullable=False),
        sa.Column("no_diagnosis", sa.Boolean(), nullable=False),
        sa.Column("cbt_based", sa.Boolean(), nullable=False),
        sa.Column("safe_response", sa.Boolean(), nullable=False),
        sa.Column("referral_when_needed", sa.Boolean(), nullable=False),
        sa.Column("no_medication_advice", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("no_overclaiming", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("note_enc", sa.LargeBinary()),
        sa.Column("response_revision_id", UUID(as_uuid=True),
                  sa.ForeignKey("ai_response_revisions.id")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "decision IN ('approve','edit','reject','need_improvement')",
            name="moderation_reviews_decision_check"),
        sa.CheckConstraint(
            "decision NOT IN ('approve','edit') OR "
            "(empathy AND no_diagnosis AND cbt_based AND safe_response "
            "AND referral_when_needed AND no_medication_advice AND no_overclaiming)",
            name="moderation_reviews_checklist_check"),
    )
    op.create_index("idx_moderation_reviews_queue_time", "moderation_reviews",
                    ["queue_item_id", "created_at"])
    op.create_index("idx_moderation_reviews_reviewer_time", "moderation_reviews",
                    ["reviewer_id", "created_at"])

    # ---- additive columns on existing tables (all nullable, non-breaking) ----
    op.add_column("users", sa.Column("email_enc", sa.LargeBinary()))
    op.add_column("users", sa.Column("email_hash", sa.String(64)))
    op.add_column("users", sa.Column("current_risk_level", sa.String(2)))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True),
                                     server_default=sa.func.now()))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_users_email_hash", "users", ["email_hash"])
    op.create_index("idx_users_current_risk", "users",
                    ["current_risk_level", "status"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    op.add_column("conversations",
                  sa.Column("highest_risk_level", sa.String(2)))
    op.add_column("conversations",
                  sa.Column("message_count", sa.Integer(), nullable=False,
                            server_default="0"))

    op.add_column("drafts",
                  sa.Column("source_user_message_id", UUID(as_uuid=True),
                            sa.ForeignKey("ai_messages.id")))


def downgrade():
    op.drop_column("drafts", "source_user_message_id")
    op.drop_column("conversations", "message_count")
    op.drop_column("conversations", "highest_risk_level")
    op.drop_index("idx_users_current_risk", table_name="users")
    op.drop_constraint("uq_users_email_hash", "users", type_="unique")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "current_risk_level")
    op.drop_column("users", "email_hash")
    op.drop_column("users", "email_enc")

    op.drop_table("moderation_reviews")
    op.drop_table("moderation_queue")
    op.drop_table("ai_response_revisions")
    op.drop_table("specialist_assignments")
    op.drop_table("ai_messages")
    op.drop_table("user_profiles")
    op.drop_index("idx_admin_users_role_status", table_name="admin_users")
    op.drop_table("admin_users")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
