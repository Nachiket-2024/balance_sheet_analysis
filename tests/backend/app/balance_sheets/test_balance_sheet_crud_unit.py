# tests/backend/app/balance_sheets/test_balance_sheet_crud_unit.py
#
# Unit coverage for balance_sheet_crud.py's yfinance-import path and its
# race-condition handling. No HTTP client, but real DB (needs a real
# Company row to satisfy the company_id FK).
import uuid

import pandas as pd
import pytest
import pytest_asyncio

from backend.app.balance_sheets.balance_sheet_crud import (
    YFinanceFetchError,
    _fetch_balance_sheet_row_sync,
    get_balance_sheet,
    import_balance_sheet,
    list_balance_sheets_for_company_years,
)
from backend.app.balance_sheets.balance_sheet_model import BalanceSheet
from backend.app.companies.company_crud import create_company
from backend.app.companies.company_schema import CompanyCreate
from backend.mystic_auth.database.connection import database

MODULE = "backend.app.balance_sheets.balance_sheet_crud"


def _unique_ticker() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


@pytest_asyncio.fixture
async def company():
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Test Co", ticker=_unique_ticker()), session)
        company_id = company.id
    yield company
    async with database.async_session() as session:
        row = await session.get(type(company), company_id)
        if row:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_import_raises_when_yfinance_has_no_data(company, mocker):
    mocker.patch(f"{MODULE}._fetch_balance_sheet_row_sync", return_value=None)

    async with database.async_session() as session:
        with pytest.raises(ValueError, match="No yfinance balance sheet data"):
            await import_balance_sheet(company.id, 2023, company.ticker, session)


def test_fetch_wraps_yfinance_failures_as_yfinance_fetch_error(mocker):
    """A network/Yahoo-side failure (timeout, HTTP error, malformed response)
    must not propagate as a raw, unhandled exception, since the route layer only
    knows how to translate ValueError (no data) and YFinanceFetchError
    (fetch failed), so anything else would surface as an opaque 500."""
    mocker.patch(f"{MODULE}.yf.Ticker", side_effect=ConnectionError("network unreachable"))

    with pytest.raises(YFinanceFetchError, match="Failed to fetch balance sheet"):
        _fetch_balance_sheet_row_sync("AAPL", 2023)


def test_fetch_returns_sanitized_requested_year(mocker):
    stock = mocker.Mock()
    stock.balance_sheet = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [123.0, 45.0]},
        index=["Total Assets", "Total Debt"],
    )
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=stock)

    result = _fetch_balance_sheet_row_sync("AAPL", 2023)

    assert result["total_assets"] == 123.0
    assert result["total_debt"] == 45.0


def test_fetch_returns_none_for_empty_or_unrequested_year(mocker):
    empty_stock = mocker.Mock()
    empty_stock.balance_sheet = pd.DataFrame()
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=empty_stock)
    assert _fetch_balance_sheet_row_sync("AAPL", 2023) is None

    dated_stock = mocker.Mock()
    dated_stock.balance_sheet = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [123.0]}, index=["Total Assets"]
    )
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=dated_stock)
    assert _fetch_balance_sheet_row_sync("AAPL", 2022) is None


@pytest.mark.asyncio
async def test_import_propagates_yfinance_fetch_error_uncaught(company, mocker):
    """import_balance_sheet doesn't swallow a fetch failure into the
    already-exists/no-data ValueError path: it's a distinct error the route
    layer maps to 502, not 400."""
    mocker.patch(f"{MODULE}._fetch_balance_sheet_row_sync", side_effect=YFinanceFetchError("boom"))

    async with database.async_session() as session:
        with pytest.raises(YFinanceFetchError, match="boom"):
            await import_balance_sheet(company.id, 2023, company.ticker, session)


@pytest.mark.asyncio
async def test_import_persists_mocked_yfinance_fields(company, mocker):
    mocker.patch(
        f"{MODULE}._fetch_balance_sheet_row_sync",
        return_value={"total_assets": 1_000_000.0, "total_debt": 200_000.0, "not_a_real_column": 999},
    )

    async with database.async_session() as session:
        result = await import_balance_sheet(company.id, 2023, company.ticker, session)

    assert result.total_assets == 1_000_000.0
    assert result.total_debt == 200_000.0
    # Defensive filter (see import_balance_sheet's docstring): an unmapped
    # key from a sanitized yfinance row is silently dropped, not persisted
    # or raised as an error.
    assert not hasattr(result, "not_a_real_column") or result.not_a_real_column != 999

    async with database.async_session() as session:
        row = await get_balance_sheet(company.id, 2023, session)
        assert row is not None
        await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_import_raises_value_error_when_row_already_exists(company, mocker):
    mocker.patch(f"{MODULE}._fetch_balance_sheet_row_sync", return_value={"total_assets": 1.0})

    async with database.async_session() as session:
        await import_balance_sheet(company.id, 2024, company.ticker, session)

    async with database.async_session() as session:
        with pytest.raises(ValueError, match="already exists"):
            await import_balance_sheet(company.id, 2024, company.ticker, session)

    async with database.async_session() as session:
        row = await get_balance_sheet(company.id, 2024, session)
        await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_import_race_condition_is_translated_to_value_error(company, mocker):
    """
    The pre-insert existence check (get_balance_sheet) isn't atomic with the
    insert, so this simulates a concurrent request winning that race by
    pre-inserting the row directly, then forcing import_balance_sheet's own
    existence check to report "not found" (mocked), so its INSERT is the one
    that actually hits the uq_balance_sheet_company_year constraint and must
    be caught and translated to ValueError, not left as an unhandled
    IntegrityError (which would surface as an unhandled 500, not a clean 400).
    """
    async with database.async_session() as session:
        session.add(BalanceSheet(company_id=company.id, year=2025, total_assets=1.0))
        await session.commit()

    mocker.patch(f"{MODULE}.get_balance_sheet", return_value=None)
    mocker.patch(f"{MODULE}._fetch_balance_sheet_row_sync", return_value={"total_assets": 2.0})

    async with database.async_session() as session:
        with pytest.raises(ValueError, match="already exists"):
            await import_balance_sheet(company.id, 2025, company.ticker, session)

    async with database.async_session() as session:
        result = await session.execute(
            BalanceSheet.__table__.select().where(
                BalanceSheet.company_id == company.id, BalanceSheet.year == 2025
            )
        )
        rows = result.fetchall()
        assert len(rows) == 1  # the original row, not a duplicate
        await session.execute(
            BalanceSheet.__table__.delete().where(
                BalanceSheet.company_id == company.id, BalanceSheet.year == 2025
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_list_balance_sheets_can_filter_years(company):
    async with database.async_session() as session:
        session.add_all(
            [
                BalanceSheet(company_id=company.id, year=2022, total_assets=1),
                BalanceSheet(company_id=company.id, year=2023, total_assets=2),
            ]
        )
        await session.commit()

    async with database.async_session() as session:
        rows = await list_balance_sheets_for_company_years(company.id, [2023], session)
        assert [item.year for item in rows] == [2023]
        await session.execute(BalanceSheet.__table__.delete().where(BalanceSheet.company_id == company.id))
        await session.commit()
