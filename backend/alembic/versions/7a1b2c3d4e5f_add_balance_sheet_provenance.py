"""Add balance-sheet provenance, refresh history, and import attempts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("balance_sheets", sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True))
    op.add_column("balance_sheets", sa.Column("period_end_date", sa.Date(), nullable=True))
    op.add_column("balance_sheets", sa.Column("period_type", sa.String(length=16), server_default="annual", nullable=False))
    op.add_column("balance_sheets", sa.Column("source_provider", sa.String(length=64), server_default="yfinance", nullable=False))
    op.add_column("balance_sheets", sa.Column("source_url", sa.String(length=1024), nullable=True))
    op.add_column("balance_sheets", sa.Column("currency_code", sa.String(length=8), nullable=True))
    op.add_column("balance_sheets", sa.Column("unit_scale", sa.Float(), server_default="1", nullable=False))
    op.add_column("balance_sheets", sa.Column("data_quality_status", sa.String(length=32), server_default="current", nullable=False))
    op.add_column("balance_sheets", sa.Column("source_fields", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
    op.add_column("balance_sheets", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.create_index("ix_balance_sheets_imported_at", "balance_sheets", ["imported_at"], unique=False)

    op.create_table(
        "balance_sheet_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("balance_sheet_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reason", sa.String(length=32), server_default="refresh", nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["balance_sheet_id"], ["balance_sheets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_balance_sheet_snapshots_id", "balance_sheet_snapshots", ["id"], unique=False)
    op.create_index("ix_balance_sheet_snapshots_balance_sheet_id", "balance_sheet_snapshots", ["balance_sheet_id"], unique=False)
    op.create_index("ix_balance_sheet_snapshots_company_id", "balance_sheet_snapshots", ["company_id"], unique=False)
    op.create_index("ix_balance_sheet_snapshots_year", "balance_sheet_snapshots", ["year"], unique=False)

    op.create_table(
        "balance_sheet_import_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("balance_sheet_id", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), server_default="yfinance", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(["balance_sheet_id"], ["balance_sheets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_balance_sheet_import_attempts_id", "balance_sheet_import_attempts", ["id"], unique=False)
    op.create_index("ix_balance_sheet_import_attempts_company_id", "balance_sheet_import_attempts", ["company_id"], unique=False)
    op.create_index("ix_balance_sheet_import_attempts_balance_sheet_id", "balance_sheet_import_attempts", ["balance_sheet_id"], unique=False)
    op.create_index("ix_balance_sheet_import_attempts_year", "balance_sheet_import_attempts", ["year"], unique=False)
    op.create_index("ix_balance_sheet_import_attempts_status", "balance_sheet_import_attempts", ["status"], unique=False)

    op.execute("UPDATE balance_sheets SET imported_at = created_at WHERE imported_at IS NULL")
    op.alter_column("balance_sheets", "imported_at", nullable=False)


def downgrade() -> None:
    op.drop_table("balance_sheet_import_attempts")
    op.drop_table("balance_sheet_snapshots")
    op.drop_index("ix_balance_sheets_imported_at", table_name="balance_sheets")
    for column in (
        "version", "source_fields", "data_quality_status", "unit_scale", "currency_code",
        "source_url", "source_provider", "period_type", "period_end_date", "imported_at",
    ):
        op.drop_column("balance_sheets", column)
