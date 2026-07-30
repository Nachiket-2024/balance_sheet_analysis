"""split policies:manage into fine-grained authorization-management actions

Revision ID: e2b6c8a4f1d5
Revises: d9a1e5c7f3b8
Create Date: 2026-07-15 00:00:00.000000

Per claude.md's Remaining PBAC Work item #1: the single coarse
"policies:manage" action is replaced with fine-grained actions
(policies:read/create/update/delete/assign/revoke) so a caller could, in
future, be granted e.g. only policies:read (to inspect/audit) without also
being able to create, edit, delete, or (re)assign policies.

This is a pure data migration: it updates the existing seeded
`system_superuser` policy row's `actions` array in place (no schema
change). Every route that previously required "policies:manage" now
requires one of the fine-grained actions instead (see
authorization/routes/policy_routes.py) — updating this one policy row is
what keeps the system superuser able to do all of them, exactly as before.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2b6c8a4f1d5'
down_revision: str | Sequence[str] | None = 'd9a1e5c7f3b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = ["users:assign_system_role", "users:promote_to_admin", "policies:manage"]
_NEW_ACTIONS = [
    "users:assign_system_role",
    "users:promote_to_admin",
    "policies:read",
    "policies:create",
    "policies:update",
    "policies:delete",
    "policies:assign",
    "policies:revoke",
]


def upgrade() -> None:
    connection = op.get_bind()
    policies_table = sa.table(
        'policies',
        sa.column('name', sa.String),
        sa.column('actions', postgresql.ARRAY(sa.String())),
    )
    connection.execute(
        policies_table.update()
        .where(policies_table.c.name == 'system_superuser')
        .values(actions=_NEW_ACTIONS)
    )


def downgrade() -> None:
    connection = op.get_bind()
    policies_table = sa.table(
        'policies',
        sa.column('name', sa.String),
        sa.column('actions', postgresql.ARRAY(sa.String())),
    )
    connection.execute(
        policies_table.update()
        .where(policies_table.c.name == 'system_superuser')
        .values(actions=_OLD_ACTIONS)
    )
