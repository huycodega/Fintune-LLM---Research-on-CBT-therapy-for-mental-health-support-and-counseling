"""Initial schema (v4)

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, ARRAY


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String, unique=True, nullable=False),
        sa.Column("email", sa.String, unique=True),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("role", sa.String, nullable=False, server_default="user"),
        sa.Column("consent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.CheckConstraint("role IN ('user','clinician','admin')",
                            name="users_role_check"),
    )
    op.create_index("idx_users_role_nonuser", "users", ["role"],
                     postgresql_where=sa.text("role <> 'user'"))

    op.create_table(
        "intake_forms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("raw_text_enc", sa.LargeBinary, nullable=False),
        sa.Column("demographics", JSONB),
        sa.Column("presenting", sa.LargeBinary),
        sa.Column("reason", sa.Text),
        sa.Column("past_history", JSONB),
        sa.Column("functioning", JSONB),
        sa.Column("social_support", sa.Text),
        sa.Column("phq9_score", sa.SmallInteger),
        sa.Column("gad7_score", sa.SmallInteger),
        sa.Column("parser_version", sa.String),
        sa.Column("parse_confidence", sa.Float),
    )
    op.create_index("idx_intake_user", "intake_forms",
                     ["user_id", sa.text("created_at DESC")])

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("intake_id", UUID(as_uuid=True),
                  sa.ForeignKey("intake_forms.id")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("user_input_enc", sa.LargeBinary, nullable=False),
        sa.Column("user_input_hash", sa.String, nullable=False),
        sa.Column("triage_level", sa.String),
        sa.Column("triage_reason", sa.Text),
        sa.Column("severity", sa.String),
        sa.Column("confidence", sa.Float),
        sa.Column("analysis", JSONB),
        sa.Column("retrieved_ids", ARRAY(sa.String)),
        sa.Column("prompt_hash", sa.String),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("final_reply_enc", sa.LargeBinary),
        sa.Column("final_technique", sa.String),
        sa.Column("reviewed_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("triage_level IN ('L0','L1','L2','L3')",
                            name="sessions_triage_check"),
        sa.CheckConstraint(
            "status IN ('crisis','pending_review','answered','rejected','auto_sent')",
            name="sessions_status_check"),
    )
    op.create_index("idx_sessions_user_time", "sessions",
                     ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_sessions_pending", "sessions", ["status"],
                     postgresql_where=sa.text("status = 'pending_review'"))
    op.create_index("idx_sessions_triage", "sessions",
                     ["triage_level", sa.text("created_at DESC")])

    op.create_table(
        "drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("idx", sa.SmallInteger, nullable=False),
        sa.Column("technique", sa.String),
        sa.Column("rationale", sa.Text),
        sa.Column("plan", sa.Text),
        sa.Column("response_enc", sa.LargeBinary),
        sa.Column("well_formed", sa.Boolean, server_default=sa.true()),
        sa.Column("hallucination_score", sa.Float),
        sa.Column("preflight_pass", sa.Boolean),
    )
    op.create_index("idx_drafts_session", "drafts", ["session_id", "idx"])

    op.create_table(
        "review_queue",
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("triage_level", sa.String),
        sa.Column("priority", sa.SmallInteger),
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id")),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution", sa.String),
        sa.CheckConstraint("resolution IN ('approve','edit','reject')",
                            name="queue_resolution_check"),
    )
    op.create_index("idx_queue_open", "review_queue",
                     ["priority", "sla_due_at"],
                     postgresql_where=sa.text("resolved_at IS NULL"))

    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("draft_chosen", UUID(as_uuid=True),
                  sa.ForeignKey("drafts.id")),
        sa.Column("rating", sa.SmallInteger),
        sa.Column("edit_diff", JSONB),
        sa.Column("clinician_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )

    op.create_table(
        "soap_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("sessions.id"), unique=True, nullable=False),
        sa.Column("subjective_enc", sa.LargeBinary),
        sa.Column("objective", sa.Text),
        sa.Column("assessment", sa.Text),
        sa.Column("plan", sa.Text),
        sa.Column("exported_to_ehr", sa.Boolean, server_default=sa.false()),
        sa.Column("pdf_s3_key", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )

    op.create_table(
        "audit_trail",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("ts", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("actor_id", UUID(as_uuid=True)),
        sa.Column("actor_username", sa.String),
        sa.Column("actor_role", sa.String),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("resource_type", sa.String),
        sa.Column("resource_id", UUID(as_uuid=True)),
        sa.Column("ip_address", INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("detail", JSONB),
    )
    op.create_index("idx_audit_time", "audit_trail",
                     [sa.text("ts DESC")])
    op.create_index("idx_audit_actor", "audit_trail",
                     ["actor_id", sa.text("ts DESC")])
    op.create_index("idx_audit_resource", "audit_trail",
                     ["resource_type", "resource_id"])

    # HIPAA: make audit_trail append-only via DB-level revoke.
    # App role can INSERT/SELECT but never UPDATE/DELETE.
    op.execute("REVOKE UPDATE, DELETE ON audit_trail FROM PUBLIC")

    # Preference pairs view (used to export DPO training data).
    op.execute("""
        CREATE VIEW preference_pairs AS
        SELECT
            f.id AS feedback_id,
            s.user_input_hash,
            d_chosen.id AS chosen_draft_id,
            d_chosen.response_enc AS chosen_enc,
            d_rejected.id AS rejected_draft_id,
            d_rejected.response_enc AS rejected_enc
        FROM feedback f
        JOIN drafts d_chosen ON d_chosen.id = f.draft_chosen
        JOIN drafts d_rejected
            ON d_rejected.session_id = d_chosen.session_id
           AND d_rejected.id <> d_chosen.id
        JOIN sessions s ON s.id = d_chosen.session_id
    """)


def downgrade():
    op.execute("DROP VIEW IF EXISTS preference_pairs")
    op.drop_table("audit_trail")
    op.drop_table("soap_notes")
    op.drop_table("feedback")
    op.drop_table("review_queue")
    op.drop_table("drafts")
    op.drop_table("sessions")
    op.drop_table("intake_forms")
    op.drop_table("users")
