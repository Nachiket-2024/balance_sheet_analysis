"""grant permissions:grant/revoke/read to system_superuser

Revision ID: 6d6c9f178682
Revises: ddc3e944ea2f
Create Date: 2026-08-27 00:00:02.000000

Data-only migration (per docs/mystic_auth/authorization/adding-permissions.md's
documented process): grants the three new permissions:grant/revoke/read
actions (see authorization/permissions.py, added alongside the
user_permissions table in ddc3e944ea2f) to the seeded system_superuser
policy only. Granting a bare action directly to a user (bypassing Policy
entirely, see authorization/models/user_permission_model.py) is at least as
sensitive as policies:assign/revoke, so it follows the same
system_superuser-only default the original policies:assign/revoke actions
got, not the five extended (policy_management/policy_maintainer/...)
policies - an operator can extend those separately if desired.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "6d6c9f178682"
down_revision: str | None = "ddc3e944ea2f"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_OLD_ACTIONS = [
    "users:assign_system_role",
    "policies:read",
    "policies:create",
    "policies:update",
    "policies:delete",
    "policies:assign",
    "policies:revoke",
    "security_audit:read",
    "users:purge",
    "users:reactivate",
    "rate_limits:read",
    "rate_limits:reset",
]
_NEW_ACTIONS = _OLD_ACTIONS + ["permissions:grant", "permissions:revoke", "permissions:read"]


def upgrade() -> None:
    connection = op.get_bind()
    policies_table = sa.table(
        "policies",
        sa.column("name", sa.String),
        sa.column("actions", postgresql.ARRAY(sa.String())),
    )
    connection.execute(
        policies_table.update().where(policies_table.c.name == "system_superuser").values(actions=_NEW_ACTIONS)
    )


def downgrade() -> None:
    connection = op.get_bind()
    policies_table = sa.table(
        "policies",
        sa.column("name", sa.String),
        sa.column("actions", postgresql.ARRAY(sa.String())),
    )
    connection.execute(
        policies_table.update().where(policies_table.c.name == "system_superuser").values(actions=_OLD_ACTIONS)
    )
