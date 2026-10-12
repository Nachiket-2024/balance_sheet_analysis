"""Add bounded LLM provider probe history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "97b4c6d8e1f2"
down_revision: str | Sequence[str] | None = "86a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_provider_probes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("reachable", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_provider_probes_id", "llm_provider_probes", ["id"], unique=False)
    op.create_index("ix_llm_provider_probes_provider", "llm_provider_probes", ["provider"], unique=False)
    op.create_index("ix_llm_provider_probes_checked_at", "llm_provider_probes", ["checked_at"], unique=False)


def downgrade() -> None:
    op.drop_table("llm_provider_probes")
