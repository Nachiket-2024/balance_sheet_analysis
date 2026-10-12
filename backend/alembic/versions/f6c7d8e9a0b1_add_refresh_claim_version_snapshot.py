"""store the token version snapshot for idempotent refresh retries

Revision ID: f6c7d8e9a0b1
Revises: f5b6c7d8e9a0
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6c7d8e9a0b1"
down_revision: str | Sequence[str] | None = "f5b6c7d8e9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consumed_refresh_tokens",
        sa.Column("account_ver", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "consumed_refresh_tokens",
        sa.Column("chain_ver", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("consumed_refresh_tokens", "chain_ver")
    op.drop_column("consumed_refresh_tokens", "account_ver")
