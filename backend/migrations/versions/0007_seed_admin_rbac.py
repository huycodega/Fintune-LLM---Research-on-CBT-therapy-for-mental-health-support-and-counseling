"""Seed admin RBAC roles and permissions.

Admin account rows are synchronized from legacy clinician/admin users by the
application after migration. That step uses the application's AES-GCM helper,
so encrypted email values are never faked inside SQL.

Revision ID: 0007_seed_admin_rbac
Revises: 0006_user_mgmt_ai_moderation
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_seed_admin_rbac"
down_revision = "0006_user_mgmt_ai_moderation"
branch_labels = None
depends_on = None


ROLE_IDS = {
    "admin": "10000000-0000-0000-0000-000000000001",
    "manager": "10000000-0000-0000-0000-000000000002",
    "clinician": "10000000-0000-0000-0000-000000000003",
}

PERMISSIONS = {
    "users.list": "20000000-0000-0000-0000-000000000001",
    "users.pii.read": "20000000-0000-0000-0000-000000000002",
    "users.create": "20000000-0000-0000-0000-000000000003",
    "users.status": "20000000-0000-0000-0000-000000000004",
    "users.assign": "20000000-0000-0000-0000-000000000005",
    "admin_users.manage_roles": "20000000-0000-0000-0000-000000000006",
    "moderation.list": "20000000-0000-0000-0000-000000000007",
    "moderation.detail": "20000000-0000-0000-0000-000000000008",
    "moderation.claim": "20000000-0000-0000-0000-000000000009",
    "moderation.decide": "20000000-0000-0000-0000-000000000010",
    "audit.read": "20000000-0000-0000-0000-000000000011",
}


def upgrade():
    roles = sa.table("roles", sa.column("id"), sa.column("code"),
                     sa.column("name"), sa.column("description"))
    permissions = sa.table("permissions", sa.column("id"), sa.column("key"),
                           sa.column("description"))
    role_permissions = sa.table(
        "role_permissions", sa.column("role_id"), sa.column("permission_id"))

    op.bulk_insert(roles, [
        {"id": ROLE_IDS["admin"], "code": "admin", "name": "Administrator",
         "description": "Full user, moderation and RBAC access"},
        {"id": ROLE_IDS["manager"], "code": "manager", "name": "Manager",
         "description": "Read and assignment oversight"},
        {"id": ROLE_IDS["clinician"], "code": "clinician", "name": "Clinician",
         "description": "Clinical review and assigned-user access"},
    ])
    op.bulk_insert(permissions, [
        {"id": pid, "key": key, "description": key.replace(".", " ")}
        for key, pid in PERMISSIONS.items()
    ])

    admin_keys = set(PERMISSIONS)
    manager_keys = {"users.list", "users.assign", "moderation.list",
                    "moderation.detail", "audit.read"}
    clinician_keys = {"users.list", "users.pii.read", "moderation.list",
                      "moderation.detail", "moderation.claim",
                      "moderation.decide"}
    rows = []
    for role, keys in (("admin", admin_keys), ("manager", manager_keys),
                       ("clinician", clinician_keys)):
        rows.extend({"role_id": ROLE_IDS[role], "permission_id": PERMISSIONS[key]}
                    for key in sorted(keys))
    op.bulk_insert(role_permissions, rows)


def downgrade():
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE role_id IN "
        "(:admin, :manager, :clinician)"
    ).bindparams(**ROLE_IDS))
    op.execute(sa.text(
        "DELETE FROM permissions WHERE id IN ("
        + ",".join(f"'{value}'" for value in PERMISSIONS.values()) + ")"))
    op.execute(sa.text(
        "DELETE FROM roles WHERE id IN (:admin, :manager, :clinician)"
    ).bindparams(**ROLE_IDS))
