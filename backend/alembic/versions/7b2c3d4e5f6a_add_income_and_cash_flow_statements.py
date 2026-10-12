"""Add curated income-statement and cash-flow data."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b2c3d4e5f6a"
down_revision: str | Sequence[str] | None = "7a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_METRICS = (
    "total_revenue", "gross_profit", "operating_income", "ebitda", "pretax_income", "net_income",
    "operating_cash_flow", "capital_expenditure", "free_cash_flow", "investing_cash_flow",
    "financing_cash_flow", "end_cash_position",
)


def upgrade() -> None:
    columns = [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("statement_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=True),
        sa.Column("period_type", sa.String(length=16), server_default="annual", nullable=False),
        sa.Column("source_provider", sa.String(length=64), server_default="yfinance", nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=True),
        sa.Column("unit_scale", sa.Float(), server_default="1", nullable=False),
        sa.Column("data_quality_status", sa.String(length=32), server_default="current", nullable=False),
        sa.Column("source_fields", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    ]
    columns.extend(sa.Column(metric, sa.Float(), nullable=True) for metric in _METRICS)
    op.create_table(
        "financial_statements",
        *columns,
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "statement_type", "year", name="uq_financial_statement_period"),
    )
    for column in ("id", "company_id", "statement_type", "year", "imported_at"):
        op.create_index(f"ix_financial_statements_{column}", "financial_statements", [column], unique=False)

    op.create_table(
        "financial_statement_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("financial_statement_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("statement_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reason", sa.String(length=32), server_default="refresh", nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["financial_statement_id"], ["financial_statements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "financial_statement_id", "company_id", "statement_type", "year"):
        op.create_index(f"ix_financial_statement_snapshots_{column}", "financial_statement_snapshots", [column], unique=False)

    op.create_table(
        "financial_statement_import_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("financial_statement_id", sa.Integer(), nullable=True),
        sa.Column("statement_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), server_default="yfinance", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["financial_statement_id"], ["financial_statements.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "company_id", "financial_statement_id", "statement_type", "year", "status"):
        op.create_index(f"ix_financial_statement_import_attempts_{column}", "financial_statement_import_attempts", [column], unique=False)


def downgrade() -> None:
    op.drop_table("financial_statement_import_attempts")
    op.drop_table("financial_statement_snapshots")
    op.drop_table("financial_statements")
