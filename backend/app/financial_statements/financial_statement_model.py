from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..app_sdk import Base

if TYPE_CHECKING:
    from ..companies.company_model import Company
else:
    from ..companies.company_model import Company


FINANCIAL_STATEMENT_COLUMNS: tuple[str, ...] = (
    "total_revenue",
    "gross_profit",
    "operating_income",
    "ebitda",
    "pretax_income",
    "net_income",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "end_cash_position",
)


class FinancialStatement(Base):
    """Curated annual income or cash-flow metrics for one company and year."""

    __tablename__ = "financial_statements"
    __table_args__ = (UniqueConstraint("company_id", "statement_type", "year", "period_type", "period_number", name="uq_financial_statement_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    statement_type: Mapped[str] = mapped_column(String(16), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    period_number: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    period_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_type: Mapped[str] = mapped_column(String(16), default="annual", server_default="annual")
    source_provider: Mapped[str] = mapped_column(String(64), default="yfinance", server_default="yfinance")
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unit_scale: Mapped[float] = mapped_column(default=1.0, server_default="1")
    data_quality_status: Mapped[str] = mapped_column(String(32), default="current", server_default="current")
    source_fields: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    total_revenue: Mapped[float | None]
    gross_profit: Mapped[float | None]
    operating_income: Mapped[float | None]
    ebitda: Mapped[float | None]
    pretax_income: Mapped[float | None]
    net_income: Mapped[float | None]
    operating_cash_flow: Mapped[float | None]
    capital_expenditure: Mapped[float | None]
    free_cash_flow: Mapped[float | None]
    investing_cash_flow: Mapped[float | None]
    financing_cash_flow: Mapped[float | None]
    end_cash_position: Mapped[float | None]

    company: Mapped[Company] = relationship()


class FinancialStatementSnapshot(Base):
    __tablename__ = "financial_statement_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    financial_statement_id: Mapped[int] = mapped_column(ForeignKey("financial_statements.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    statement_type: Mapped[str] = mapped_column(String(16), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    period_type: Mapped[str] = mapped_column(String(16), default="annual", server_default="annual")
    period_number: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str] = mapped_column(String(32), default="refresh", server_default="refresh")
    values: Mapped[dict[str, Any]] = mapped_column(JSON)


class FinancialStatementImportAttempt(Base):
    __tablename__ = "financial_statement_import_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    financial_statement_id: Mapped[int | None] = mapped_column(ForeignKey("financial_statements.id", ondelete="SET NULL"), nullable=True, index=True)
    statement_type: Mapped[str] = mapped_column(String(16), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    period_type: Mapped[str] = mapped_column(String(16), default="annual", server_default="annual")
    period_number: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    provider: Mapped[str] = mapped_column(String(64), default="yfinance", server_default="yfinance")
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
