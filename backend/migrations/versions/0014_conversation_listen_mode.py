"""listen_mode on conversations — durable "just listen" state (was Redis-only)

Revision ID: 0014_conversation_listen_mode
Revises: 0013_journal_entries
"""
import sqlalchemy as sa
from alembic import op

revision = "0014_conversation_listen_mode"
down_revision = "0013_journal_entries"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = [c["name"] for c in insp.get_columns("conversations")]
    if "listen_mode" not in cols:
        op.add_column("conversations",
                      sa.Column("listen_mode", sa.Boolean(), nullable=False,
                                server_default="false"))


def downgrade():
    op.drop_column("conversations", "listen_mode")
