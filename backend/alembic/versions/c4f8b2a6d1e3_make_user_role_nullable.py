"""make users.role nullable

Revision ID: c4f8b2a6d1e3
Revises: b7d3a1c9e4f2
Create Date: 2026-07-13 00:30:00.000000

Per claude.md's PBAC spec, role must be pure metadata (display/grouping)
and never an authorization mechanism — and the system "must support ...
users without roles". A NOT NULL role column makes that literally
impossible: every user is forced to carry a role value even though nothing
in the authorization path (AuthorizationService / PolicyEvaluationEngine)
reads it anymore. This migration only relaxes the constraint; it does not
change any existing data (every current row keeps its existing role value)
or default (new rows via signup_service still default to role="user" for
display purposes — see that module for why the default itself is unchanged).
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4f8b2a6d1e3'
down_revision: str | Sequence[str] | None = 'b7d3a1c9e4f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('users', 'role', nullable=True)


def downgrade() -> None:
    """
    NOTE: if any row has role IS NULL at this point, re-adding NOT NULL
    will fail — an operator downgrading past this point must first backfill
    a role for any such row (e.g. UPDATE users SET role = 'user' WHERE role
    IS NULL).
    """
    op.alter_column('users', 'role', nullable=False)
