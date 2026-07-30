"""add companies and balance_sheets tables

Revision ID: c1a2b3c4d5e6
Revises: b2c3d4e5f6a7
Create Date: 2026-07-25 00:00:00.000000

Introduces this app's own domain schema (backend/app/, not
backend/mystic_auth/) on top of the template's PBAC/auth tables:

  - companies: self-referential (parent_company_id) company/vertical
    hierarchy, plus a denormalized group_root_id — see
    backend/app/companies/company_model.py's docstring for why
    group_root_id exists (PBAC's resource_attributes condition only
    supports flat equality, not a recursive parent walk, so "grant access
    to a whole group" needs a flat column to match on).
  - balance_sheets: one row per (company_id, year), with a real FK to
    companies replacing the pre-migration repo's unenforced
    `ticker == Company.name` string join.

No policy seeding happens here (unlike mystic_auth's own
b7d3a1c9e4f2_add_pbac_policies.py) — this app's policies are conditioned on
real company_id/group_root_id values that don't exist until actual
companies are created, so seeding company-scoped policies is a data-seeding
concern (backend/app/seed/seed_demo_data.py), not a schema migration.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: str | Sequence[str] | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The ~68 nullable yfinance-sourced Float columns on balance_sheets — kept as
# a single list here so create_table/downgrade don't repeat ~68 lines twice.
# Must match backend/app/balance_sheets/balance_sheet_model.py exactly.
_YFINANCE_COLUMNS = [
    "treasury_shares_number", "ordinary_shares_number", "share_issued", "net_debt", "total_debt",
    "tangible_book_value", "invested_capital", "working_capital", "net_tangible_assets",
    "capital_lease_obligations", "common_stock_equity", "total_capitalization",
    "total_equity_gross_minority_interest", "stockholders_equity",
    "gains_losses_not_affecting_retained_earnings", "other_equity_adjustments", "retained_earnings",
    "capital_stock", "common_stock", "total_liabilities_net_minority_interest",
    "total_non_current_liabilities_net_minority_interest", "other_non_current_liabilities",
    "trade_and_other_payables_non_current", "long_term_debt_and_capital_lease_obligation",
    "long_term_capital_lease_obligation", "long_term_debt", "current_liabilities",
    "other_current_liabilities", "current_deferred_liabilities", "current_deferred_revenue",
    "current_debt_and_capital_lease_obligation", "current_capital_lease_obligation", "current_debt",
    "other_current_borrowings", "commercial_paper", "payables_and_accrued_expenses", "payables",
    "total_tax_payable", "income_tax_payable", "accounts_payable", "total_assets",
    "total_non_current_assets", "other_non_current_assets", "non_current_deferred_assets",
    "non_current_deferred_taxes_assets", "investments_and_advances", "other_investments",
    "investment_in_financial_assets", "available_for_sale_securities", "net_ppe",
    "accumulated_depreciation", "gross_ppe", "leases", "other_properties",
    "machinery_furniture_equipment", "land_and_improvements", "properties", "current_assets",
    "other_current_assets", "inventory", "receivables", "other_receivables", "accounts_receivable",
    "cash_cash_equivalents_and_short_term_investments", "other_short_term_investments",
    "cash_and_cash_equivalents", "cash_equivalents", "cash_financial",
]


def upgrade() -> None:
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('parent_company_id', sa.Integer(), nullable=True),
        sa.Column('group_root_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['parent_company_id'], ['companies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_companies_id'), 'companies', ['id'], unique=False)
    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=False)
    op.create_index(op.f('ix_companies_ticker'), 'companies', ['ticker'], unique=True)
    op.create_index(op.f('ix_companies_parent_company_id'), 'companies', ['parent_company_id'], unique=False)
    op.create_index(op.f('ix_companies_group_root_id'), 'companies', ['group_root_id'], unique=False)

    balance_sheet_columns = [
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    ]
    balance_sheet_columns += [sa.Column(name, sa.Float(), nullable=True) for name in _YFINANCE_COLUMNS]

    op.create_table(
        'balance_sheets',
        *balance_sheet_columns,
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'year', name='uq_balance_sheet_company_year'),
    )
    op.create_index(op.f('ix_balance_sheets_id'), 'balance_sheets', ['id'], unique=False)
    op.create_index(op.f('ix_balance_sheets_company_id'), 'balance_sheets', ['company_id'], unique=False)
    op.create_index(op.f('ix_balance_sheets_year'), 'balance_sheets', ['year'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_balance_sheets_year'), table_name='balance_sheets')
    op.drop_index(op.f('ix_balance_sheets_company_id'), table_name='balance_sheets')
    op.drop_index(op.f('ix_balance_sheets_id'), table_name='balance_sheets')
    op.drop_table('balance_sheets')

    op.drop_index(op.f('ix_companies_group_root_id'), table_name='companies')
    op.drop_index(op.f('ix_companies_parent_company_id'), table_name='companies')
    op.drop_index(op.f('ix_companies_ticker'), table_name='companies')
    op.drop_index(op.f('ix_companies_name'), table_name='companies')
    op.drop_index(op.f('ix_companies_id'), table_name='companies')
    op.drop_table('companies')
