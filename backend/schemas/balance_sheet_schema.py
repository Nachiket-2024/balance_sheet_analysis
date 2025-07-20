# Import the BaseModel class and ConfigDict for model configuration
from pydantic import BaseModel, ConfigDict

# Base schema for balance sheet data, reused for input/output
class BalanceSheetBase(BaseModel):
    # Required fields
    ticker: str  # Stock ticker (e.g., AAPL, TSLA)
    year: int  # Reporting year (e.g., 2024, 2023)

    # Optional financial fields (can be null)
    treasury_shares_number: float | None = None
    ordinary_shares_number: float | None = None
    share_issued: float | None = None
    net_debt: float | None = None
    total_debt: float | None = None
    tangible_book_value: float | None = None
    invested_capital: float | None = None
    working_capital: float | None = None
    net_tangible_assets: float | None = None
    capital_lease_obligations: float | None = None
    common_stock_equity: float | None = None
    total_capitalization: float | None = None
    total_equity_gross_minority_interest: float | None = None
    stockholders_equity: float | None = None
    gains_losses_not_affecting_retained_earnings: float | None = None
    other_equity_adjustments: float | None = None
    retained_earnings: float | None = None
    capital_stock: float | None = None
    common_stock: float | None = None
    total_liabilities_net_minority_interest: float | None = None
    total_non_current_liabilities_net_minority_interest: float | None = None
    other_non_current_liabilities: float | None = None
    trade_and_other_payables_non_current: float | None = None
    long_term_debt_and_capital_lease_obligation: float | None = None
    long_term_capital_lease_obligation: float | None = None
    long_term_debt: float | None = None
    current_liabilities: float | None = None
    other_current_liabilities: float | None = None
    current_deferred_liabilities: float | None = None
    current_deferred_revenue: float | None = None
    current_debt_and_capital_lease_obligation: float | None = None
    current_capital_lease_obligation: float | None = None
    current_debt: float | None = None
    other_current_borrowings: float | None = None
    commercial_paper: float | None = None
    payables_and_accrued_expenses: float | None = None
    payables: float | None = None
    total_tax_payable: float | None = None
    income_tax_payable: float | None = None
    accounts_payable: float | None = None
    total_assets: float | None = None
    total_non_current_assets: float | None = None
    other_non_current_assets: float | None = None
    non_current_deferred_assets: float | None = None
    non_current_deferred_taxes_assets: float | None = None
    investments_and_advances: float | None = None
    other_investments: float | None = None
    investment_in_financial_assets: float | None = None
    available_for_sale_securities: float | None = None
    net_ppe: float | None = None
    accumulated_depreciation: float | None = None
    gross_ppe: float | None = None
    leases: float | None = None
    other_properties: float | None = None
    machinery_furniture_equipment: float | None = None
    land_and_improvements: float | None = None
    properties: float | None = None
    current_assets: float | None = None
    other_current_assets: float | None = None
    inventory: float | None = None
    receivables: float | None = None
    other_receivables: float | None = None
    accounts_receivable: float | None = None
    cash_cash_equivalents_and_short_term_investments: float | None = None
    other_short_term_investments: float | None = None
    cash_and_cash_equivalents: float | None = None
    cash_equivalents: float | None = None
    cash_financial: float | None = None

    # Config for Pydantic to enable ORM mode using SQLAlchemy attributes
    class Config(ConfigDict):
        from_attributes = True


# Schema for returning a balance sheet, includes primary key
class BalanceSheetOut(BalanceSheetBase):

    class Config(ConfigDict):
        from_attributes = True


# Schema for returning company details
class CompanyOut(BaseModel):
    name: str  # Ticker used as company name
    industry: str | None = None  # Optional industry info

    class Config(ConfigDict):
        from_attributes = True


# Schema for returning a company with its associated balance sheets
class CompanyWithBalanceSheets(BaseModel):
    company: CompanyOut  # Company info
    balance_sheets: list[BalanceSheetOut]  # List of balance sheet entries

    class Config(ConfigDict):
        from_attributes = True
