"""merge migration branches

Revision ID: 2056f1b0bfeb
Revises: 6d6c9f178682, c1a2b3c4d5e6
Create Date: 2026-09-06 00:00:00.000000

This app's own c1a2b3c4d5e6 (companies/balance_sheets tables) and
upstream's 6d6c9f178682 (grant/revoke/read permissions for
system_superuser) both forked off the same prior head, so a sync-upstream
run left two alembic heads. No schema change of its own: purely a join
point so `alembic upgrade head` has a single target again. See
scripts/mystic_auth/upstream-sync/check-alembic-heads.sh and
docs/mystic_auth/template-usage/syncing-upstream.md.
"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '2056f1b0bfeb'
down_revision: str | Sequence[str] | None = ('6d6c9f178682', 'c1a2b3c4d5e6')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
