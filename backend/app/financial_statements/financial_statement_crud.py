import asyncio
from datetime import UTC, date, datetime
from typing import Any, Literal

import yfinance as yf
from curl_cffi import requests as curl_requests
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..balance_sheets.balance_sheet_crud import YFinanceFetchError
from ..balance_sheets.sanitize_fields import sanitize_dict
from .financial_statement_model import (
    FINANCIAL_STATEMENT_COLUMNS,
    FinancialStatement,
    FinancialStatementImportAttempt,
    FinancialStatementSnapshot,
)

StatementType = Literal["income", "cash_flow"]
_TIMEOUT_SECONDS = 15

_FIELD_MAP: dict[str, dict[str, tuple[str, ...]]] = {
    "income": {
        "total_revenue": ("Total Revenue", "Operating Revenue"),
        "gross_profit": ("Gross Profit",),
        "operating_income": ("Operating Income",),
        "ebitda": ("EBITDA",),
        "pretax_income": ("Pretax Income",),
        "net_income": ("Net Income", "Net Income Common Stockholders"),
    },
    "cash_flow": {
        "operating_cash_flow": ("Operating Cash Flow", "Total Cash From Operating Activities"),
        "capital_expenditure": ("Capital Expenditure",),
        "free_cash_flow": ("Free Cash Flow",),
        "investing_cash_flow": ("Investing Cash Flow",),
        "financing_cash_flow": ("Financing Cash Flow",),
        "end_cash_position": ("End Cash Position", "Changes In Cash"),
    },
}


def _fetch_statement_sync(ticker: str, statement_type: StatementType, year: int, period_type: str = "annual", period_number: int = 0) -> dict[str, Any] | None:
    try:
        session: curl_requests.Session = curl_requests.Session(impersonate="chrome", timeout=_TIMEOUT_SECONDS)
        stock = yf.Ticker(ticker, session=session)
        if statement_type == "income":
            frame = stock.income_stmt if period_type == "annual" else stock.quarterly_income_stmt
        else:
            frame = stock.cashflow if period_type == "annual" else stock.quarterly_cashflow
    except Exception as exc:
        raise YFinanceFetchError(f"Failed to fetch {statement_type} statement for '{ticker}': {exc}") from exc

    if frame.empty:
        return None
    frame = frame.T
    row = next((frame.loc[index] for index in frame.index if index.year == year and (period_type == "annual" or index.quarter == period_number)), None)
    if row is None:
        return None

    fields: dict[str, Any] = {}
    source_fields: list[str] = []
    for target, candidates in _FIELD_MAP[statement_type].items():
        for source in candidates:
            value = row.get(source)
            if value is not None:
                fields[target] = value
                source_fields.append(source)
                break
    fields = sanitize_dict(fields)
    currency_code = None
    try:
        fast_info = stock.fast_info
        if hasattr(fast_info, "get"):
            candidate = fast_info.get("currency")
            currency_code = candidate.upper() if isinstance(candidate, str) else None
    except Exception:
        currency_code = None
    period_end = row.name
    fields.update(
        {
            "_period_end_date": period_end.date() if hasattr(period_end, "date") else None,
            "_source_provider": "yfinance",
            "_source_url": f"https://finance.yahoo.com/quote/{ticker.upper()}/{statement_type}",
            "_source_fields": source_fields,
            "_unit_scale": 1.0,
            "_currency_code": currency_code,
            "_period_type": period_type,
            "_period_number": period_number,
        }
    )
    return fields


async def _start_attempt(company_id: int, statement_type: StatementType, year: int, period_type: str, period_number: int, db: AsyncSession) -> FinancialStatementImportAttempt:
    attempt = FinancialStatementImportAttempt(company_id=company_id, statement_type=statement_type, year=year, period_type=period_type, period_number=period_number, status="running")
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def _finish_attempt(attempt_id: int, db: AsyncSession, *, status: str, statement_id: int | None = None, source_url: str | None = None, error: str | None = None) -> None:
    attempt = await db.get(FinancialStatementImportAttempt, attempt_id)
    if attempt is None:
        return
    attempt.status = status
    attempt.financial_statement_id = statement_id
    attempt.source_url = source_url
    attempt.error_message = error[:2048] if error else None
    attempt.completed_at = datetime.now(UTC)
    await db.commit()


def _snapshot_values(statement: FinancialStatement) -> dict[str, Any]:
    values = {field: getattr(statement, field) for field in FINANCIAL_STATEMENT_COLUMNS}
    values.update({
        "period_end_date": statement.period_end_date.isoformat() if statement.period_end_date else None,
        "period_type": statement.period_type,
        "period_number": statement.period_number,
        "source_provider": statement.source_provider,
        "source_url": statement.source_url,
        "currency_code": statement.currency_code,
        "unit_scale": statement.unit_scale,
        "data_quality_status": statement.data_quality_status,
        "source_fields": statement.source_fields,
        "version": statement.version,
    })
    return values


async def get_statement(company_id: int, statement_type: StatementType, year: int, db: AsyncSession, period_type: str = "annual", period_number: int = 0) -> FinancialStatement | None:
    result = await db.execute(select(FinancialStatement).where(
        FinancialStatement.company_id == company_id,
        FinancialStatement.statement_type == statement_type,
        FinancialStatement.year == year,
        FinancialStatement.period_type == period_type,
        FinancialStatement.period_number == period_number,
    ))
    return result.scalar_one_or_none()


async def list_statements(company_id: int, statement_type: StatementType | None, db: AsyncSession, years: list[int] | None = None, period_type: str | None = None) -> list[FinancialStatement]:
    query = select(FinancialStatement).where(FinancialStatement.company_id == company_id)
    if statement_type:
        query = query.where(FinancialStatement.statement_type == statement_type)
    if years:
        query = query.where(FinancialStatement.year.in_(years))
    if period_type:
        query = query.where(FinancialStatement.period_type == period_type)
    result = await db.execute(query.order_by(FinancialStatement.statement_type, FinancialStatement.year, FinancialStatement.period_number))
    return list(result.scalars().all())


async def import_statement(company_id: int, statement_type: StatementType, year: int, ticker: str, db: AsyncSession, *, refresh: bool = False, period_type: str = "annual", period_number: int = 0) -> FinancialStatement:
    if period_type not in {"annual", "quarterly"} or (period_type == "quarterly" and period_number not in {1, 2, 3, 4}) or (period_type == "annual" and period_number != 0):
        raise ValueError("period_type must be annual or quarterly, with quarter 1-4 for quarterly periods")
    attempt = await _start_attempt(company_id, statement_type, year, period_type, period_number, db)
    existing = await get_statement(company_id, statement_type, year, db, period_type, period_number)
    if existing is not None and not refresh:
        message = f"{statement_type} statement for company {company_id}, year {year} already exists"
        await _finish_attempt(attempt.id, db, status="rejected", error=message)
        raise ValueError(message)
    try:
        fields = await asyncio.to_thread(_fetch_statement_sync, ticker, statement_type, year, period_type, period_number)
        if fields is None:
            message = f"No yfinance {statement_type} statement data for ticker '{ticker}', year {year}"
            await _finish_attempt(attempt.id, db, status="no_data", error=message)
            raise ValueError(message)
        known = {key: value for key, value in fields.items() if key in FINANCIAL_STATEMENT_COLUMNS}
        period_end = fields.get("_period_end_date")
        if not isinstance(period_end, date):
            period_end = None
        source_url = fields.get("_source_url")
        source_fields: list[str] = [str(value) for value in fields.get("_source_fields", [])] if isinstance(fields.get("_source_fields"), list) else []
        if existing is None:
            statement = FinancialStatement(company_id=company_id, statement_type=statement_type, year=year, **known)
            db.add(statement)
        else:
            db.add(FinancialStatementSnapshot(
                financial_statement_id=existing.id,
                company_id=existing.company_id,
                statement_type=existing.statement_type,
                year=existing.year,
                period_type=existing.period_type,
                period_number=existing.period_number,
                version=existing.version,
                values=_snapshot_values(existing),
            ))
            statement = existing
            for field in FINANCIAL_STATEMENT_COLUMNS:
                setattr(statement, field, known.get(field))
            statement.version = (statement.version or 1) + 1
        statement.imported_at = datetime.now(UTC)
        statement.period_end_date = period_end
        statement.period_type = fields.get("_period_type") or "annual"
        statement.period_number = int(fields.get("_period_number") or 0)
        statement.source_provider = fields.get("_source_provider") or "yfinance"
        statement.source_url = source_url
        statement.currency_code = fields.get("_currency_code")
        statement.unit_scale = float(fields.get("_unit_scale") or 1.0)
        statement.data_quality_status = "current"
        statement.source_fields = source_fields
        await db.commit()
        await db.refresh(statement)
        await _finish_attempt(attempt.id, db, status="success", statement_id=statement.id, source_url=source_url)
        return statement
    except IntegrityError as exc:
        await db.rollback()
        message = f"{statement_type} statement for company {company_id}, year {year} already exists"
        await _finish_attempt(attempt.id, db, status="rejected", error=message)
        raise ValueError(message) from exc
    except YFinanceFetchError as exc:
        await _finish_attempt(attempt.id, db, status="failed", error=str(exc))
        raise
