"""Record bounded LLM usage without retaining user prompts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "83d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "82c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(length=320), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_chars", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_chars", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "user_email", "company_id", "status", "created_at"):
        op.create_index(f"ix_llm_usage_{column}", "llm_usage", [column], unique=False)


def downgrade() -> None:
    op.drop_table("llm_usage")
