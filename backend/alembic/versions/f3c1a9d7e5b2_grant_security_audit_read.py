"""grant security_audit:read to system_superuser

Revision ID: f3c1a9d7e5b2
Revises: a8d4f6c2b9e7
Create Date: 2026-07-13 00:00:01.000000

Data-only migration (per docs/mystic_auth/authorization/adding-permissions.md's documented
process): grants the new security_audit:read permission (see
authorization/permissions.py) to the seeded system_superuser policy only.
This is a security log covering all users' auth events, not scoped to
user_administration's day-to-day account management.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3c1a9d7e5b2'
down_revision: str | Sequence[str] | None = 'a8d4f6c2b9e7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = [
    "users:assign_system_role",
    "users:promote_to_admin",
    "policies:read",
    "policies:create",
    "policies:update",
    "policies:delete",
    "policies:assign",
    "policies:revoke",
]
_NEW_ACTIONS = _OLD_ACTIONS + ["security_audit:read"]


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
