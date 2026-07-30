"""add authorization audit log table

Revision ID: d9a1e5c7f3b8
Revises: c4f8b2a6d1e3
Create Date: 2026-07-14 00:00:00.000000

Adds the persistent audit trail for authorization decisions per
claude.md's Remaining PBAC Work item #1 ("Authorization decisions must be
auditable ... Automatically log every authorize() call"). Every real call
to AuthorizationService.authorize()/require() (i.e. every protected route
hit) now writes one row here — see authorization_service.py's
_log_decision. The table has no foreign keys to policies/users
deliberately: an audit entry must keep reflecting exactly what was
evaluated at the time even if the policy or user referenced is later
renamed or deleted (see AuthorizationAuditLog's own docstring).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd9a1e5c7f3b8'
down_revision: str | Sequence[str] | None = 'c4f8b2a6d1e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'authorization_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_email', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_identifier', sa.String(), nullable=True),
        sa.Column('allowed', sa.Boolean(), nullable=False),
        sa.Column('candidate_policy_names', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('granting_policy_names', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_authorization_audit_log_id'), 'authorization_audit_log', ['id'], unique=False)
    op.create_index(
        op.f('ix_authorization_audit_log_user_email'), 'authorization_audit_log', ['user_email'], unique=False
    )
    op.create_index(
        op.f('ix_authorization_audit_log_action'), 'authorization_audit_log', ['action'], unique=False
    )
    op.create_index(
        op.f('ix_authorization_audit_log_created_at'), 'authorization_audit_log', ['created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_authorization_audit_log_created_at'), table_name='authorization_audit_log')
    op.drop_index(op.f('ix_authorization_audit_log_action'), table_name='authorization_audit_log')
    op.drop_index(op.f('ix_authorization_audit_log_user_email'), table_name='authorization_audit_log')
    op.drop_index(op.f('ix_authorization_audit_log_id'), table_name='authorization_audit_log')
    op.drop_table('authorization_audit_log')
