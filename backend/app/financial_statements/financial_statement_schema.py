from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StatementType = Literal["income", "cash_flow"]


class FinancialStatementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    statement_type: StatementType
    year: int
    period_number: int = 0
    created_at: datetime
    imported_at: datetime
    period_end_date: date | None = None
    period_type: str = "annual"
    source_provider: str = "yfinance"
    source_url: str | None = None
    currency_code: str | None = None
    unit_scale: float = 1.0
    data_quality_status: str = "current"
    source_fields: list[str] = Field(default_factory=list)
    version: int = 1
    total_revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    ebitda: float | None = None
    pretax_income: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    free_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    end_cash_position: float | None = None
