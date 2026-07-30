import asyncio

import yfinance as yf
from curl_cffi import requests as curl_requests
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .balance_sheet_model import YFINANCE_COLUMN_NAMES, BalanceSheet
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


def _fetch_balance_sheet_row_sync(ticker: str, year: int) -> dict | None:
    """
    Blocking network call (yfinance has no async API); always run this via
    asyncio.to_thread from a route/service, never awaited directly. Returns
    the sanitized {db_field: value} mapping for the requested fiscal year, or
    None if yfinance has no data for that ticker/year.

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
    return sanitize_dict(raw_fields)


async def import_balance_sheet(company_id: int, year: int, ticker: str, db: AsyncSession) -> BalanceSheet:
    """
    Fetches `ticker`'s balance sheet for `year` from yfinance and persists it
    against `company_id`. Raises ValueError if yfinance has no data for that
    ticker/year, or if a row for this (company_id, year) already exists;
    the route layer translates both into the appropriate HTTP status.
    """
    existing = await get_balance_sheet(company_id, year, db)
    if existing is not None:
        raise ValueError(f"Balance sheet for company {company_id}, year {year} already exists")

    fields = await asyncio.to_thread(_fetch_balance_sheet_row_sync, ticker, year)
    if fields is None:
        raise ValueError(f"No yfinance balance sheet data for ticker '{ticker}', year {year}")

    # Only accept keys that are real BalanceSheet columns, defensive
    # against yfinance ever introducing a label this app doesn't map.
    known_fields = {key: value for key, value in fields.items() if key in YFINANCE_COLUMN_NAMES}

    balance_sheet = BalanceSheet(company_id=company_id, year=year, **known_fields)
    db.add(balance_sheet)
    try:
        await db.commit()
    except IntegrityError as exc:
        # The existence check above isn't atomic with this insert, so a
        # concurrent request for the same (company_id, year) can still race
        # past it and hit the uq_balance_sheet_company_year constraint here.
        # Translated to the same ValueError the pre-insert check raises, so
        # the route layer's single except-ValueError branch covers both.
        await db.rollback()
        raise ValueError(f"Balance sheet for company {company_id}, year {year} already exists") from exc
    await db.refresh(balance_sheet)
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
