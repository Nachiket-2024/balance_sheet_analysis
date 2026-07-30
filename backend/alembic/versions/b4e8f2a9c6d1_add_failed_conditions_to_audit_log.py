"""add failed_conditions to authorization_audit_log

Revision ID: b4e8f2a9c6d1
Revises: a3f7c9e1b2d4
Create Date: 2026-07-13 00:00:00.000000

Per claude.md's Authorization Decision Explainability: audit logs must be
able to explain *why* access was denied, not just that it was. This adds
one nullable JSONB column capturing {policy_name: [failed_condition_key,
...]} for every candidate policy whose conditions did not pass — see
evaluators/authorization_decision.py's `failed_conditions` field, which
this column persists.

Purely additive (nullable, no default required for existing rows) — no
backfill needed, since older rows simply never had this information
computed.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4e8f2a9c6d1'
down_revision: str | Sequence[str] | None = 'a3f7c9e1b2d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'authorization_audit_log',
        sa.Column('failed_conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('authorization_audit_log', 'failed_conditions')
