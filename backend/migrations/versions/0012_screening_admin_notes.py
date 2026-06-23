"""clinician notes on screenings

Revision ID: 0012_screening_admin_notes
Revises: 0011_user_profiles
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012_screening_admin_notes"
down_revision = "0011_user_profiles"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = [c["name"] for c in insp.get_columns("screenings")]
    if "admin_notes" not in cols:
        op.add_column("screenings", sa.Column("admin_notes", JSONB()))


def downgrade():
    op.drop_column("screenings", "admin_notes")
