from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..app_sdk import Base

if TYPE_CHECKING:
    # Import guarded: company_model.py doesn't import this module, so this
    # isn't a real cycle, but keeping it TYPE_CHECKING-only means mypy sees
    # the real type for the relationship() below without adding an actual
    # runtime dependency between the two feature folders.
    from ..companies.company_model import Company


class BalanceSheet(Base):
    """
    One company's reported balance sheet for one fiscal year. company_id is
    a real FK (see company_model.py) replacing the old repo's unenforced
    `ticker == Company.name` string join.

    Every field below is a nullable Float sourced from yfinance, since a given
    company/year may be missing any individual line item depending on what
    yfinance actually reported for it. Field list ported unchanged from the
    pre-migration repo (to_arrange/backend/models/balance_sheet_model.py);
    see yfinance_field_map.py for the yfinance-label -> column-name mapping.
    """

    __tablename__ = "balance_sheets"
    __table_args__ = (UniqueConstraint("company_id", "year", name="uq_balance_sheet_company_year"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)

    # Explicit DateTime(timezone=True), see company_model.py's own comment
    # on the same pattern.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship()

    treasury_shares_number: Mapped[float | None]
    ordinary_shares_number: Mapped[float | None]
    share_issued: Mapped[float | None]
    net_debt: Mapped[float | None]
    total_debt: Mapped[float | None]
    tangible_book_value: Mapped[float | None]
    invested_capital: Mapped[float | None]
    working_capital: Mapped[float | None]
    net_tangible_assets: Mapped[float | None]
    capital_lease_obligations: Mapped[float | None]
    common_stock_equity: Mapped[float | None]
    total_capitalization: Mapped[float | None]
    total_equity_gross_minority_interest: Mapped[float | None]
    stockholders_equity: Mapped[float | None]
    gains_losses_not_affecting_retained_earnings: Mapped[float | None]
    other_equity_adjustments: Mapped[float | None]
    retained_earnings: Mapped[float | None]
    capital_stock: Mapped[float | None]
    common_stock: Mapped[float | None]
    total_liabilities_net_minority_interest: Mapped[float | None]
    total_non_current_liabilities_net_minority_interest: Mapped[float | None]
    other_non_current_liabilities: Mapped[float | None]
    trade_and_other_payables_non_current: Mapped[float | None]
    long_term_debt_and_capital_lease_obligation: Mapped[float | None]
    long_term_capital_lease_obligation: Mapped[float | None]
    long_term_debt: Mapped[float | None]
    current_liabilities: Mapped[float | None]
    other_current_liabilities: Mapped[float | None]
    current_deferred_liabilities: Mapped[float | None]
    current_deferred_revenue: Mapped[float | None]
    current_debt_and_capital_lease_obligation: Mapped[float | None]
    current_capital_lease_obligation: Mapped[float | None]
    current_debt: Mapped[float | None]
    other_current_borrowings: Mapped[float | None]
    commercial_paper: Mapped[float | None]
    payables_and_accrued_expenses: Mapped[float | None]
    payables: Mapped[float | None]
    total_tax_payable: Mapped[float | None]
    income_tax_payable: Mapped[float | None]
    accounts_payable: Mapped[float | None]
    total_assets: Mapped[float | None]
    total_non_current_assets: Mapped[float | None]
    other_non_current_assets: Mapped[float | None]
    non_current_deferred_assets: Mapped[float | None]
    non_current_deferred_taxes_assets: Mapped[float | None]
    investments_and_advances: Mapped[float | None]
    other_investments: Mapped[float | None]
    investment_in_financial_assets: Mapped[float | None]
    available_for_sale_securities: Mapped[float | None]
    net_ppe: Mapped[float | None]
    accumulated_depreciation: Mapped[float | None]
    gross_ppe: Mapped[float | None]
    leases: Mapped[float | None]
    other_properties: Mapped[float | None]
    machinery_furniture_equipment: Mapped[float | None]
    land_and_improvements: Mapped[float | None]
    properties: Mapped[float | None]
    current_assets: Mapped[float | None]
    other_current_assets: Mapped[float | None]
    inventory: Mapped[float | None]
    receivables: Mapped[float | None]
    other_receivables: Mapped[float | None]
    accounts_receivable: Mapped[float | None]
    cash_cash_equivalents_and_short_term_investments: Mapped[float | None]
    other_short_term_investments: Mapped[float | None]
    cash_and_cash_equivalents: Mapped[float | None]
    cash_equivalents: Mapped[float | None]
    cash_financial: Mapped[float | None]


# The full set of yfinance-sourced column names above, used by
# balance_sheet_crud.py to know which sanitized-dict keys are valid model
# fields when constructing a BalanceSheet from an imported row, without
# accepting arbitrary/unexpected keys from a sanitized yfinance row.
YFINANCE_COLUMN_NAMES: tuple[str, ...] = (
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
)
