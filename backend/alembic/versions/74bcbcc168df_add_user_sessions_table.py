"""add user sessions table

Revision ID: 74bcbcc168df
Revises: b2c3d4e5f6a7
Create Date: 2026-08-01 00:00:00.000000

Adds the persistent, per-session tracking backing the "Manage Sessions"
dashboard card: one row per login session (device/browser, IP, first-seen,
last-used), independent of (but kept in sync with) the actual Redis-backed
account/chain version counters that govern real token validity
(jwt_service.py). Refresh tokens rotate their jti on every /auth/refresh
call, so `current_jti` tracks whichever jti currently represents a session
while `chain_id` stays stable across rotation and `id` stays the stable
identifier surfaced to and revoked by the client - see session_model.py.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '74bcbcc168df'
down_revision: str | Sequence[str] | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('current_jti', sa.String(), nullable=False),
        # Stable per-login identity, unchanged across every rotation of
        # this session (unlike current_jti, which is single-use and
        # rotates on every /auth/refresh call): what a single-session
        # revoke or logout actually invalidates in Redis (jwt_service's
        # chain_ver:{email}:{chain_id} counter), and what ties every row's
        # rotations back to the one login that started it. Nullable since
        # sessions predating this column carry none.
        sa.Column('chain_id', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_sessions_id'), 'user_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_sessions_current_jti'), 'user_sessions', ['current_jti'], unique=True)
    op.create_index(op.f('ix_user_sessions_chain_id'), 'user_sessions', ['chain_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_sessions_chain_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_current_jti'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
