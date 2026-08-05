"""remove stale promote-to-admin policy action

Revision ID: d6e7f8a9b0c1
Revises: 74bcbcc168df
Create Date: 2026-08-04 00:00:00.000000

Data-only migration: the one-way promote endpoint was replaced by
PATCH /users/{user_email}/role, which checks users:assign_role or
users:assign_system_role. No route checks users:promote_to_admin anymore.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | Sequence[str] | None = "74bcbcc168df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE policies
            SET actions = array_remove(actions, 'users:promote_to_admin')
            WHERE 'users:promote_to_admin' = ANY(actions)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE policies
            SET actions = array_append(actions, 'users:promote_to_admin')
            WHERE name = 'system_superuser'
              AND NOT ('users:promote_to_admin' = ANY(actions))
            """
        )
    )
