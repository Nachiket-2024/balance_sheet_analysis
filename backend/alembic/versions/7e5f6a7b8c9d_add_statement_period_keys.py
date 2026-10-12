"""Allow annual and quarterly statement periods."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7e5f6a7b8c9d"
down_revision: str | Sequence[str] | None = "7d4e5f6a7b8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("financial_statements", sa.Column("period_number", sa.Integer(), server_default="0", nullable=False))
    op.drop_constraint("uq_financial_statement_period", "financial_statements", type_="unique")
    op.create_unique_constraint(
        "uq_financial_statement_period",
        "financial_statements",
        ["company_id", "statement_type", "year", "period_type", "period_number"],
    )
    op.add_column("financial_statement_snapshots", sa.Column("period_type", sa.String(length=16), server_default="annual", nullable=False))
    op.add_column("financial_statement_snapshots", sa.Column("period_number", sa.Integer(), server_default="0", nullable=False))
    op.add_column("financial_statement_import_attempts", sa.Column("period_type", sa.String(length=16), server_default="annual", nullable=False))
    op.add_column("financial_statement_import_attempts", sa.Column("period_number", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("financial_statement_import_attempts", "period_number")
    op.drop_column("financial_statement_import_attempts", "period_type")
    op.drop_column("financial_statement_snapshots", "period_number")
    op.drop_column("financial_statement_snapshots", "period_type")
    op.drop_constraint("uq_financial_statement_period", "financial_statements", type_="unique")
    op.create_unique_constraint("uq_financial_statement_period", "financial_statements", ["company_id", "statement_type", "year"])
    op.drop_column("financial_statements", "period_number")
