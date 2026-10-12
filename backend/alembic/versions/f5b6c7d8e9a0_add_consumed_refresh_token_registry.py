"""add durable consumed refresh token registry

Revision ID: f5b6c7d8e9a0
Revises: f4a1c2e8b7d6
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5b6c7d8e9a0"
down_revision: str | Sequence[str] | None = "f4a1c2e8b7d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consumed_refresh_tokens",
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index("ix_consumed_refresh_tokens_expires_at", "consumed_refresh_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_consumed_refresh_tokens_expires_at", table_name="consumed_refresh_tokens")
    op.drop_table("consumed_refresh_tokens")
