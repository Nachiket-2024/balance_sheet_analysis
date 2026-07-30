"""add policy_history table for policy versioning and rollback

Revision ID: a3f7c9e1b2d4
Revises: e2b6c8a4f1d5
Create Date: 2026-07-13 00:00:00.000000

Per claude.md's Remaining Backend PBAC Production Hardening item #1
(Policy Versioning and Change History): every policy mutation
(create/update/delete/rollback) must produce an immutable history entry so
policy changes are fully traceable and reversible.

Deliberately no foreign key to `policies` — mirrors
authorization_audit_log's own rationale (see that migration): a policy
referenced by an old history entry may since have been edited or deleted,
and the history must keep reflecting exactly what existed *at the time*.
`policy_name` is the durable identifier used to query a policy's full
history even after the policy row itself is gone.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f7c9e1b2d4'
down_revision: str | Sequence[str] | None = 'e2b6c8a4f1d5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'policy_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=True),
        sa.Column('policy_name', sa.String(), nullable=False),
        sa.Column('change_type', sa.String(), nullable=False),
        sa.Column('previous_definition', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_definition', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('changed_fields', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('changed_by', sa.String(), nullable=True),
        sa.Column('change_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_policy_history_id'), 'policy_history', ['id'], unique=False)
    op.create_index(op.f('ix_policy_history_policy_id'), 'policy_history', ['policy_id'], unique=False)
    op.create_index(op.f('ix_policy_history_policy_name'), 'policy_history', ['policy_name'], unique=False)
    op.create_index(op.f('ix_policy_history_created_at'), 'policy_history', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_policy_history_created_at'), table_name='policy_history')
    op.drop_index(op.f('ix_policy_history_policy_name'), table_name='policy_history')
    op.drop_index(op.f('ix_policy_history_policy_id'), table_name='policy_history')
    op.drop_index(op.f('ix_policy_history_id'), table_name='policy_history')
    op.drop_table('policy_history')
