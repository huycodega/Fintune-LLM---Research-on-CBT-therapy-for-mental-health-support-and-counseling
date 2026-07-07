"""collaborative safety plans — one per user, PHI-encrypted

Revision ID: 0015_safety_plans
Revises: 0014_conversation_listen_mode
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0015_safety_plans"
down_revision = "0014_conversation_listen_mode"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "safety_plans" in insp.get_table_names():
        return
    op.create_table(
        "safety_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        # AES-256-GCM encrypted JSON of the six Stanley-Brown sections
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("safety_plans")
