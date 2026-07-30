"""add system role

Revision ID: f2754349a6c7
Revises: f45a54f398cb
Create Date: 2026-04-11 11:50:11.593430

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2754349a6c7'
down_revision: str | Sequence[str] | None = 'f45a54f398cb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adds new role 'system' to existing PostgreSQL enum type."""
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'system'")


def downgrade() -> None:
    """No-op: PostgreSQL does not support removing enum values."""
    pass