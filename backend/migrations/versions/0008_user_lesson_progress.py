"""Per-user lesson progress

Revision ID: 0008_user_lesson_progress
Revises: 0007_seed_admin_rbac
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0008_user_lesson_progress"
down_revision = "0007_seed_admin_rbac"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_lesson_progress",
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("lesson_id", UUID(as_uuid=True),
                  sa.ForeignKey("lessons.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("completed_steps", JSONB()),
        sa.Column("status", sa.String(), nullable=False,
                  server_default="in_progress"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_index("idx_user_lesson_progress_user",
                    "user_lesson_progress", ["user_id"])


def downgrade():
    op.drop_index("idx_user_lesson_progress_user",
                  table_name="user_lesson_progress")
    op.drop_table("user_lesson_progress")
