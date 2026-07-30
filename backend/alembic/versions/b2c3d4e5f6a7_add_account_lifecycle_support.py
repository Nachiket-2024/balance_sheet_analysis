"""add account lifecycle support (soft delete + purge/reactivate permissions)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 00:00:01.000000

Schema + data migration:
1. Adds users.deleted_at (nullable timestamp) — the soft-delete marker.
   NULL means never deleted; set on soft delete, cleared on reactivation.
2. Grants the two new lifecycle permissions (users:purge, users:reactivate
   — see authorization/permissions.py) to the seeded system_superuser
   policy, following the same process docs/mystic_auth/authorization/adding-permissions.md
   documents (mirrors f3c1a9d7e5b2's grant of security_audit:read).
   Deliberately NOT granted to user_administration: hard delete
   (irreversible data destruction) and reactivation (restoring access) are
   both more sensitive than day-to-day account management.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
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
    "security_audit:read",
]
_NEW_ACTIONS = _OLD_ACTIONS + ["users:purge", "users:reactivate"]


def upgrade() -> None:
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

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

    op.drop_column('users', 'deleted_at')
