"""per-day personalised screening plan

Revision ID: 0010_screening_plans
Revises: 0008_app_settings
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010_screening_plans"
down_revision = "0008_app_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "screening_plans",
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("plan_date", sa.Date(), primary_key=True),
        sa.Column("instrument", sa.String(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("intro", sa.Text()),
        sa.Column("ai_intro", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("screening_plans")
