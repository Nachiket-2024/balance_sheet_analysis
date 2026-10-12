"""grant rate_limits:read to system_superuser

Revision ID: c4d5e6f7a8b9
Revises: d6e7f8a9b0c1
Create Date: 2026-08-19 00:00:00.000000

Data-only migration (per docs/mystic_auth/authorization/adding-permissions.md's
documented process): grants the new rate_limits:read permission (see
authorization/permissions.py) to the seeded system_superuser policy only.
Live Valkey rate-limit state is operational/security-sensitive in the same
way the security audit trail is, so it gets the same treatment as
f3c1a9d7e5b2's grant of security_audit:read.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: str | Sequence[str] | None = 'd6e7f8a9b0c1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE policies
            SET actions = array_append(actions, 'rate_limits:read')
            WHERE name = 'system_superuser'
              AND NOT ('rate_limits:read' = ANY(actions))
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE policies
            SET actions = array_remove(actions, 'rate_limits:read')
            WHERE name = 'system_superuser'
            """
        )
    )
