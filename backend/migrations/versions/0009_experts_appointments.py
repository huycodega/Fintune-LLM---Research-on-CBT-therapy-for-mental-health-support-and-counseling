"""Psychologists + appointments (expert consultation booking)

Revision ID: 0009_experts_appointments
Revises: 0008_user_lesson_progress
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0009_experts_appointments"
down_revision = "0008_user_lesson_progress"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "psychologists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String()),
        sa.Column("experience", sa.Text()),
        sa.Column("specialty", sa.String()),
        sa.Column("bio", sa.Text()),
        sa.Column("slots", JSONB()),
        sa.Column("active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_index("idx_psychologists_active", "psychologists", ["active"])

    op.create_table(
        "appointments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("psychologist_id", UUID(as_uuid=True),
                  sa.ForeignKey("psychologists.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False,
                  server_default="pending"),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','accepted','cancelled','declined')",
            name="appointments_status_check"),
    )
    op.create_index("idx_appointments_user", "appointments", ["user_id"])
    op.create_index("idx_appointments_expert_date", "appointments",
                    ["psychologist_id", "date"])


def downgrade():
    op.drop_index("idx_appointments_expert_date", table_name="appointments")
    op.drop_index("idx_appointments_user", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("idx_psychologists_active", table_name="psychologists")
    op.drop_table("psychologists")
