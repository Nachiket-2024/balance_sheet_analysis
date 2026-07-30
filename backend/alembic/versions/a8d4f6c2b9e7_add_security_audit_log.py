"""add security audit log table

Revision ID: a8d4f6c2b9e7
Revises: c7f1a3e9d2b6
Create Date: 2026-07-13 00:00:00.000000

Adds the persistent audit trail for security-sensitive auth events (login,
logout, signup, OAuth2 login, password reset, account verification, account
lockout, refresh-token reuse detection) — per claude.md Phase 8's audit
logging requirement. Mirrors authorization_audit_log's design: no foreign
keys to users (user_email is a snapshot, not a reference, so the trail
survives account deletion), append-only, written best-effort by
audit/services/security_audit_service.py's log_security_event so a logging
failure can never break the real action it describes.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a8d4f6c2b9e7'
down_revision: str | Sequence[str] | None = 'c7f1a3e9d2b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'security_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_email', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_security_audit_log_id'), 'security_audit_log', ['id'], unique=False)
    op.create_index(
        op.f('ix_security_audit_log_user_email'), 'security_audit_log', ['user_email'], unique=False
    )
    op.create_index(
        op.f('ix_security_audit_log_event_type'), 'security_audit_log', ['event_type'], unique=False
    )
    op.create_index(
        op.f('ix_security_audit_log_created_at'), 'security_audit_log', ['created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_security_audit_log_created_at'), table_name='security_audit_log')
    op.drop_index(op.f('ix_security_audit_log_event_type'), table_name='security_audit_log')
    op.drop_index(op.f('ix_security_audit_log_user_email'), table_name='security_audit_log')
    op.drop_index(op.f('ix_security_audit_log_id'), table_name='security_audit_log')
    op.drop_table('security_audit_log')
