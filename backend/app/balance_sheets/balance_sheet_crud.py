import asyncio
from datetime import UTC, date, datetime
from typing import Any

import yfinance as yf
from curl_cffi import requests as curl_requests
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .balance_sheet_model import (
    YFINANCE_COLUMN_NAMES,
    BalanceSheet,
    BalanceSheetImportAttempt,
    BalanceSheetSnapshot,
)
from .sanitize_fields import sanitize_dict
from .yfinance_field_map import YFINANCE_TO_DB_FIELDS

# yfinance has no built-in request timeout, so a hung/slow Yahoo response would
# otherwise tie up an asyncio.to_thread worker indefinitely. yfinance requires
# its session to be a curl_cffi Session with browser impersonation
# specifically (Yahoo blocks plain requests/urllib3 clients), true across the
# 0.2.x -> 1.x line, re-verified when this project moved onto yfinance 1.5.2.
# yfinance/data.py's own default is curl_cffi.requests.Session(impersonate=
# "chrome"); this mirrors that exactly, only adding a timeout.
_YFINANCE_TIMEOUT_SECONDS = 15


class YFinanceFetchError(RuntimeError):
    """A yfinance/network failure while fetching data, distinct from "no
    data for this ticker/year" (a ValueError, a normal not-found case, not a
    failure). The route layer maps this to 502, ValueError to 400."""


def _fetch_balance_sheet_row_sync(ticker: str, year: int) -> dict[str, Any] | None:
    """
    Blocking network call (yfinance has no async API); always run this via
    asyncio.to_thread from a route/service, never awaited directly. Returns
    the sanitized field mapping plus underscore-prefixed provenance metadata
    for the requested fiscal year, or None if yfinance has no data for that
    ticker/year.

    Raises YFinanceFetchError for anything else going wrong (network error,
    Yahoo API error, malformed response), since yfinance's own exception types
    aren't a small fixed set (requests errors, its own YFException subclasses
    depending on version), so this catches broadly rather than trying to
    enumerate them all and missing one.
    """
    try:
        session: curl_requests.Session = curl_requests.Session(
            impersonate="chrome", timeout=_YFINANCE_TIMEOUT_SECONDS
        )
        stock = yf.Ticker(ticker, session=session)
        bs = stock.balance_sheet
    except Exception as exc:
        raise YFinanceFetchError(f"Failed to fetch balance sheet for '{ticker}' from yfinance: {exc}") from exc

    bs = bs.T if not bs.empty else None
    if bs is None:
        return None

    bs_year = next((bs.loc[idx] for idx in bs.index if idx.year == year), None)
    if bs_year is None:
        return None

    raw_fields = {
        db_field: bs_year.get(yahoo_field)
        for yahoo_field, db_field in YFINANCE_TO_DB_FIELDS.items()
        if bs_year.get(yahoo_field) is not None
    }
    sanitized = sanitize_dict(raw_fields)
    period_end = bs_year.name
    period_end_date = period_end.date() if hasattr(period_end, "date") else None
    currency_code = None
    try:
        fast_info = stock.fast_info
        if hasattr(fast_info, "get"):
            candidate = fast_info.get("currency")
            currency_code = candidate.upper() if isinstance(candidate, str) else None
    except Exception:
        currency_code = None
    sanitized.update(
        {
            "_period_end_date": period_end_date,
            "_source_provider": "yfinance",
            "_source_url": f"https://finance.yahoo.com/quote/{ticker.upper()}/balance-sheet",
            "_currency_code": currency_code,
            "_unit_scale": 1.0,
            "_source_fields": [
                yahoo_field
                for yahoo_field, db_field in YFINANCE_TO_DB_FIELDS.items()
                if db_field in sanitized
            ],
        }
    )
    return sanitized


async def _start_import_attempt(company_id: int, year: int, db: AsyncSession) -> BalanceSheetImportAttempt:
    attempt = BalanceSheetImportAttempt(company_id=company_id, year=year, status="running")
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def _finish_import_attempt(
    attempt_id: int,
    db: AsyncSession,
    *,
    status: str,
    balance_sheet_id: int | None = None,
    source_url: str | None = None,
    error_message: str | None = None,
) -> None:
    attempt = await db.get(BalanceSheetImportAttempt, attempt_id)
    if attempt is None:
        return
    attempt.status = status
    attempt.balance_sheet_id = balance_sheet_id
    attempt.source_url = source_url
    attempt.error_message = error_message[:2048] if error_message else None
    attempt.completed_at = datetime.now(UTC)
    await db.commit()


def _snapshot_values(balance_sheet: BalanceSheet) -> dict[str, Any]:
    values: dict[str, Any] = {field: getattr(balance_sheet, field) for field in YFINANCE_COLUMN_NAMES}
    values.update(
        {
            "period_end_date": balance_sheet.period_end_date.isoformat() if balance_sheet.period_end_date else None,
            "period_type": balance_sheet.period_type,
            "source_provider": balance_sheet.source_provider,
            "source_url": balance_sheet.source_url,
            "currency_code": balance_sheet.currency_code,
            "unit_scale": balance_sheet.unit_scale,
            "data_quality_status": balance_sheet.data_quality_status,
            "source_fields": balance_sheet.source_fields,
            "version": balance_sheet.version,
        }
    )
    return values


async def import_balance_sheet(
    company_id: int,
    year: int,
    ticker: str,
    db: AsyncSession,
    *,
    refresh: bool = False,
) -> BalanceSheet:
    """
    Fetches `ticker`'s balance sheet for `year` from yfinance and persists it.
    A refresh snapshots the previous values before replacing the current row.
    """
    attempt = await _start_import_attempt(company_id, year, db)
    attempt_id = attempt.id
    existing = await get_balance_sheet(company_id, year, db)
    if existing is not None and not refresh:
        message = f"Balance sheet for company {company_id}, year {year} already exists"
        await _finish_import_attempt(attempt_id, db, status="rejected", error_message=message)
        raise ValueError(message)

    try:
        fields = await asyncio.to_thread(_fetch_balance_sheet_row_sync, ticker, year)
    except YFinanceFetchError as exc:
        await _finish_import_attempt(attempt_id, db, status="failed", error_message=str(exc))
        raise
    if fields is None:
        message = f"No yfinance balance sheet data for ticker '{ticker}', year {year}"
        await _finish_import_attempt(attempt_id, db, status="no_data", error_message=message)
        raise ValueError(message)

    # Only accept keys that are real BalanceSheet columns, defensive
    # against yfinance ever introducing a label this app doesn't map.
    known_fields = {key: value for key, value in fields.items() if key in YFINANCE_COLUMN_NAMES}

    period_end_date = fields.get("_period_end_date")
    if not isinstance(period_end_date, date):
        period_end_date = None
    source_url = fields.get("_source_url")
    source_fields = fields.get("_source_fields")
    if not isinstance(source_fields, list):
        source_fields = []

    if existing is None:
        balance_sheet = BalanceSheet(company_id=company_id, year=year, **known_fields)
        db.add(balance_sheet)
    else:
        db.add(
            BalanceSheetSnapshot(
                balance_sheet_id=existing.id,
                company_id=existing.company_id,
                year=existing.year,
                version=existing.version,
                reason="refresh",
                values=_snapshot_values(existing),
            )
        )
        balance_sheet = existing
        for field in YFINANCE_COLUMN_NAMES:
            setattr(balance_sheet, field, known_fields.get(field))
        balance_sheet.version = (balance_sheet.version or 1) + 1

    balance_sheet.imported_at = datetime.now(UTC)
    balance_sheet.period_end_date = period_end_date
    balance_sheet.period_type = "annual"
    balance_sheet.source_provider = fields.get("_source_provider") or "yfinance"
    balance_sheet.source_url = source_url
    balance_sheet.currency_code = fields.get("_currency_code")
    balance_sheet.unit_scale = float(fields.get("_unit_scale") or 1.0)
    balance_sheet.data_quality_status = "current"
    balance_sheet.source_fields = source_fields
    try:
        await db.commit()
    except IntegrityError as exc:
        # The existence check above isn't atomic with this insert, so a
        # concurrent request for the same (company_id, year) can still race
        # past it and hit the uq_balance_sheet_company_year constraint here.
        # Translated to the same ValueError the pre-insert check raises, so
        # the route layer's single except-ValueError branch covers both.
        await db.rollback()
        message = f"Balance sheet for company {company_id}, year {year} already exists"
        await _finish_import_attempt(attempt_id, db, status="rejected", error_message=message)
        raise ValueError(message) from exc
    await db.refresh(balance_sheet)
    await _finish_import_attempt(
        attempt_id,
        db,
        status="success",
        balance_sheet_id=balance_sheet.id,
        source_url=source_url,
    )
    return balance_sheet


async def get_balance_sheet(company_id: int, year: int, db: AsyncSession) -> BalanceSheet | None:
    result = await db.execute(
        select(BalanceSheet).where(BalanceSheet.company_id == company_id, BalanceSheet.year == year)
    )
    return result.scalar_one_or_none()


async def list_balance_sheets_for_company(company_id: int, db: AsyncSession) -> list[BalanceSheet]:
    result = await db.execute(
        select(BalanceSheet).where(BalanceSheet.company_id == company_id).order_by(BalanceSheet.year)
    )
    return list(result.scalars().all())


async def list_balance_sheets_for_company_years(
    company_id: int, years: list[int] | None, db: AsyncSession
) -> list[BalanceSheet]:
    """Same as list_balance_sheets_for_company, optionally narrowed to
    specific fiscal years. Used by llm_routes.py to ground a chat request
    in only the years the caller asked about (None = every year on file)."""
    stmt = select(BalanceSheet).where(BalanceSheet.company_id == company_id)
    if years:
        stmt = stmt.where(BalanceSheet.year.in_(years))
    result = await db.execute(stmt.order_by(BalanceSheet.year))
    return list(result.scalars().all())


async def delete_balance_sheet(balance_sheet: BalanceSheet, db: AsyncSession) -> None:
    await db.delete(balance_sheet)
    await db.commit()
