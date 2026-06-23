"""extend user_profiles for the user app + saved_resources

Revision ID: 0011_user_profiles
Revises: 0010_screening_plans

Adds the self-service profile/preference columns the user app's Profile and
Settings pages persist, onto the EXISTING user_profiles table (created by
0006), plus a saved_resources bookmark table.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0011_user_profiles"
down_revision = "0010_screening_plans"
branch_labels = None
depends_on = None


def _has_column(insp, table, col) -> bool:
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {
        "wellness_goal": sa.Column("wellness_goal", sa.Text()),
        "avatar_url": sa.Column("avatar_url", sa.String()),
        "prefs": sa.Column("prefs", JSONB()),
        "consent": sa.Column("consent", JSONB()),
        "consent_updated_at": sa.Column("consent_updated_at",
                                        sa.DateTime(timezone=True)),
    }
    for name, col in cols.items():
        if not _has_column(insp, "user_profiles", name):
            op.add_column("user_profiles", col)

    if "saved_resources" not in insp.get_table_names():
        op.create_table(
            "saved_resources",
            sa.Column("user_id", UUID(as_uuid=True),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("resource_id", UUID(as_uuid=True),
                      sa.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now()),
        )


def downgrade():
    op.drop_table("saved_resources")
    for name in ("consent_updated_at", "consent", "prefs", "avatar_url",
                 "wellness_goal"):
        op.drop_column("user_profiles", name)
