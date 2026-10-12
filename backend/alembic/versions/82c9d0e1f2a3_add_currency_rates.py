"""Add explicit, company-scoped currency conversion rates."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "82c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "81b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "currency_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_currency", sa.String(length=8), nullable=False),
        sa.Column("target_currency", sa.String(length=8), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "source_currency", "target_currency", "effective_date", name="uq_currency_rate_period"),
    )
    for column in ("id", "company_id", "source_currency", "target_currency", "effective_date"):
        op.create_index(f"ix_currency_rates_{column}", "currency_rates", [column], unique=False)


def downgrade() -> None:
    op.drop_table("currency_rates")
