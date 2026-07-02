"""user journal entries — private by default, opt-in share with clinician

Revision ID: 0013_journal_entries
Revises: 0012_screening_admin_notes
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0013_journal_entries"
down_revision = "0012_screening_admin_notes"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "journal_entries" in insp.get_table_names():
        return
    op.create_table(
        "journal_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
        sa.Column("mood", sa.SmallInteger()),
        sa.Column("shared_with_clinician", sa.Boolean(), nullable=False,
                  server_default="false"),
    )
    op.create_index("idx_journal_user", "journal_entries",
                    ["user_id", sa.text("created_at DESC")])


def downgrade():
    op.drop_table("journal_entries")
