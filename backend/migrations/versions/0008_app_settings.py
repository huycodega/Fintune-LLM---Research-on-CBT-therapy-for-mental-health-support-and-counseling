"""App settings — admin system configuration (key/value per section).

Revision ID: 0008_app_settings
Revises: 0007_seed_admin_rbac
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_app_settings"
# Chained after the local experts/appointments migration so Alembic keeps a
# single linear head (both this and 0008_user_lesson_progress originally
# branched off 0007).
down_revision = "0009_experts_appointments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_settings",
        sa.Column("section", sa.String(40), primary_key=True),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column("updated_by", sa.String()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("app_settings")
