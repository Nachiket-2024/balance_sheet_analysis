"""grant rate_limits:reset to system_superuser

Revision ID: 44a59c2f57a3
Revises: a4c1e8f2b6d3
Create Date: 2026-08-19 00:00:00.000000

Data-only migration (per docs/mystic_auth/authorization/adding-permissions.md's
documented process): grants the new rate_limits:reset permission (see
authorization/permissions.py) to the seeded system_superuser policy, the only
seeded policy that previously held rate_limits:read (c4d5e6f7a8b9). Splits
DELETE /rate-limits/{key} off rate_limits:read so a future policy scoped to
"can view the rate-limit dashboard" doesn't also imply "can clear anyone's
counters" - see docs/mystic_auth/concerns/README.md's former "rate_limits:read
also grants clearing counters" entry.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '44a59c2f57a3'
down_revision: str | Sequence[str] | None = 'a4c1e8f2b6d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE policies
            SET actions = array_append(actions, 'rate_limits:reset')
            WHERE name = 'system_superuser'
              AND NOT ('rate_limits:reset' = ANY(actions))
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE policies
            SET actions = array_remove(actions, 'rate_limits:reset')
            WHERE name = 'system_superuser'
            """
        )
    )
