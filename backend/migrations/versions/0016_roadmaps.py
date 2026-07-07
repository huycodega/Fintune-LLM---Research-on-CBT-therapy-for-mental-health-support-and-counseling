"""wellness roadmaps — time-bound improvement journeys, PHI-encrypted

Revision ID: 0016_roadmaps
Revises: 0015_safety_plans
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0016_roadmaps"
down_revision = "0015_safety_plans"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "roadmaps" in insp.get_table_names():
        return
    op.create_table(
        "roadmaps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        # active | completed | archived
        sa.Column("status", sa.String(), nullable=False,
                  server_default="active"),
        # AES-256-GCM encrypted JSON: {title, goal, timeframe, steps:[{text,
        # when, done, done_at}]}
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
    )
    op.create_index("idx_roadmaps_user", "roadmaps", ["user_id", "status"])


def downgrade():
    op.drop_index("idx_roadmaps_user", table_name="roadmaps")
    op.drop_table("roadmaps")
