"""Store minimal, scoped feedback on grounded LLM answers."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "80a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "7f6a7b8c9d0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(length=320), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "company_id", "user_email"):
        op.create_index(f"ix_llm_feedback_{column}", "llm_feedback", [column], unique=False)


def downgrade() -> None:
    op.drop_table("llm_feedback")
