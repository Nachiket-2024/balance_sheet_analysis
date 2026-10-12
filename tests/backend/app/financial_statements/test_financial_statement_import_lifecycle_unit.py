from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.balance_sheets.balance_sheet_crud import YFinanceFetchError
from backend.app.financial_statements.financial_statement_crud import (
    _fetch_statement_sync,
    _finish_attempt,
    get_statement,
    import_statement,
    list_statements,
)
from backend.app.financial_statements.financial_statement_model import (
    FINANCIAL_STATEMENT_COLUMNS,
    FinancialStatement,
    FinancialStatementSnapshot,
)

MODULE = "backend.app.financial_statements.financial_statement_crud"


class Result:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


def fake_db():
    return SimpleNamespace(
        add=Mock(),
        execute=AsyncMock(),
        get=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
        refresh=AsyncMock(),
    )


def test_fetch_quarterly_statement_selects_requested_period_and_currency(mocker):
    stock = mocker.Mock()
    stock.quarterly_income_stmt = pd.DataFrame(
        {
            pd.Timestamp("2024-03-31"): [10, 4],
            pd.Timestamp("2024-06-30"): [20, 8],
        },
        index=["Operating Revenue", "Net Income Common Stockholders"],
    )
    stock.fast_info = {"currency": "usd"}
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=stock)

    result = _fetch_statement_sync("abc", "income", 2024, "quarterly", 2)

    assert result["total_revenue"] == 20
    assert result["net_income"] == 8
    assert result["_period_end_date"] == date(2024, 6, 30)
    assert result["_period_type"] == "quarterly"
    assert result["_period_number"] == 2
    assert result["_currency_code"] == "USD"
    assert result["_source_fields"] == ["Operating Revenue", "Net Income Common Stockholders"]


def test_fetch_returns_none_for_empty_frame_and_missing_quarter(mocker):
    stock = mocker.Mock()
    stock.quarterly_cashflow = pd.DataFrame()
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=stock)
    assert _fetch_statement_sync("ABC", "cash_flow", 2024, "quarterly", 1) is None

    stock.quarterly_cashflow = pd.DataFrame(
        {pd.Timestamp("2024-06-30"): [50]}, index=["Operating Cash Flow"]
    )
    assert _fetch_statement_sync("ABC", "cash_flow", 2024, "quarterly", 1) is None


def test_fetch_omits_bad_optional_currency_and_wraps_provider_property_errors(mocker):
    stock = mocker.Mock()
    stock.cashflow = pd.DataFrame(
        {pd.Timestamp("2024-12-31"): [100]}, index=["Operating Cash Flow"]
    )
    stock.fast_info = {"currency": 5}
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=stock)
    assert _fetch_statement_sync("ABC", "cash_flow", 2024)["_currency_code"] is None

    class Stock:
        income_stmt = pd.DataFrame(
            {pd.Timestamp("2024-12-31"): [100]}, index=["Total Revenue"]
        )

        @property
        def fast_info(self):
            raise RuntimeError("metadata down")

    stock = Stock()
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=stock)
    assert _fetch_statement_sync("ABC", "income", 2024)["_currency_code"] is None


@pytest.mark.asyncio
async def test_statement_queries_apply_optional_filters():
    db = fake_db()
    statement = object()
    db.execute.side_effect = [Result(scalar=statement), Result(rows=[statement])]

    assert await get_statement(3, "income", 2024, db, "quarterly", 2) is statement
    assert await list_statements(3, "income", db, [2023, 2024], "quarterly") == [statement]
    assert "period_type" in str(db.execute.call_args_list[0].args[0])
    assert "period_number" in str(db.execute.call_args_list[0].args[0])
    assert "IN" in str(db.execute.call_args_list[1].args[0])


@pytest.mark.asyncio
async def test_import_rejects_invalid_period_and_existing_row(mocker):
    db = fake_db()
    start = mocker.patch(f"{MODULE}._start_attempt", new_callable=AsyncMock)
    with pytest.raises(ValueError, match="period_type must be annual or quarterly"):
        await import_statement(3, "income", 2024, "ABC", db, period_type="monthly")
    with pytest.raises(ValueError, match="period_type must be annual or quarterly"):
        await import_statement(3, "income", 2024, "ABC", db, period_type="quarterly", period_number=0)
    start.assert_not_awaited()

    attempt = SimpleNamespace(id=22)
    existing = FinancialStatement(id=5, company_id=3, statement_type="income", year=2024)
    mocker.patch(f"{MODULE}._start_attempt", new_callable=AsyncMock, return_value=attempt)
    mocker.patch(f"{MODULE}.get_statement", new_callable=AsyncMock, return_value=existing)
    finish = mocker.patch(f"{MODULE}._finish_attempt", new_callable=AsyncMock)
    with pytest.raises(ValueError, match="already exists"):
        await import_statement(3, "income", 2024, "ABC", db)
    finish.assert_awaited_once_with(22, db, status="rejected", error="income statement for company 3, year 2024 already exists")


@pytest.mark.asyncio
async def test_import_no_data_and_provider_failure_are_recorded(mocker):
    db = fake_db()
    attempt = SimpleNamespace(id=7)
    mocker.patch(f"{MODULE}._start_attempt", new_callable=AsyncMock, return_value=attempt)
    mocker.patch(f"{MODULE}.get_statement", new_callable=AsyncMock, return_value=None)
    fetch = mocker.patch(f"{MODULE}.asyncio.to_thread", new_callable=AsyncMock, return_value=None)
    finish = mocker.patch(f"{MODULE}._finish_attempt", new_callable=AsyncMock)

    with pytest.raises(ValueError, match="No yfinance income statement data"):
        await import_statement(3, "income", 2024, "ABC", db)
    fetch.assert_awaited_once()
    finish.assert_awaited_once_with(7, db, status="no_data", error="No yfinance income statement data for ticker 'ABC', year 2024")

    finish.reset_mock()
    mocker.patch(f"{MODULE}.asyncio.to_thread", new_callable=AsyncMock, side_effect=YFinanceFetchError("offline"))
    with pytest.raises(YFinanceFetchError, match="offline"):
        await import_statement(3, "income", 2024, "ABC", db)
    finish.assert_awaited_once_with(7, db, status="failed", error="offline")


@pytest.mark.asyncio
async def test_import_creates_and_refreshes_with_snapshot_metadata(mocker):
    db = fake_db()
    db.refresh.side_effect = lambda row: setattr(row, "id", getattr(row, "id", None) or 9)
    attempt = SimpleNamespace(id=7)
    mocker.patch(f"{MODULE}._start_attempt", new_callable=AsyncMock, return_value=attempt)
    mocker.patch(f"{MODULE}._finish_attempt", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.get_statement", new_callable=AsyncMock, return_value=None)
    fields = {
        "total_revenue": 1200,
        "ignored_provider_field": 5,
        "_period_end_date": date(2024, 12, 31),
        "_period_type": "quarterly",
        "_period_number": 4,
        "_source_provider": "provider",
        "_source_url": "https://example.test/statement",
        "_source_fields": ["Total Revenue"],
        "_currency_code": "USD",
        "_unit_scale": 1000,
    }
    mocker.patch(f"{MODULE}.asyncio.to_thread", new_callable=AsyncMock, return_value=fields)

    created = await import_statement(3, "income", 2024, "ABC", db, period_type="quarterly", period_number=4)
    assert created.total_revenue == 1200
    assert created.currency_code == "USD"
    assert created.unit_scale == 1000
    assert created.source_fields == ["Total Revenue"]
    assert all(not hasattr(created, name) for name in ("ignored_provider_field",))

    existing = FinancialStatement(
        id=4,
        company_id=3,
        statement_type="income",
        year=2024,
        total_revenue=900,
        period_end_date=date(2023, 12, 31),
        period_type="annual",
        period_number=0,
        source_provider="old-provider",
        source_url="https://old.test",
        currency_code="EUR",
        unit_scale=1.0,
        data_quality_status="current",
        source_fields=["old"],
        version=2,
    )
    for column in FINANCIAL_STATEMENT_COLUMNS:
        if getattr(existing, column) is None:
            setattr(existing, column, None)
    mocker.patch(f"{MODULE}.get_statement", new_callable=AsyncMock, return_value=existing)
    snapshot_mock = mocker.patch(f"{MODULE}.FinancialStatementSnapshot", wraps=FinancialStatementSnapshot)
    refreshed = await import_statement(3, "income", 2024, "ABC", db, refresh=True)
    assert refreshed is existing
    assert existing.version == 3
    snapshot = next(call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], FinancialStatementSnapshot))
    assert snapshot.version == 2
    assert snapshot.values["total_revenue"] == 900
    snapshot_mock.assert_called_once()


@pytest.mark.asyncio
async def test_import_integrity_error_rolls_back_and_translates_conflict(mocker):
    db = fake_db()
    db.commit.side_effect = IntegrityError("insert", {}, RuntimeError("duplicate"))
    mocker.patch(f"{MODULE}._start_attempt", new_callable=AsyncMock, return_value=SimpleNamespace(id=8))
    mocker.patch(f"{MODULE}._finish_attempt", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.get_statement", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{MODULE}.asyncio.to_thread", new_callable=AsyncMock, return_value={"total_revenue": 1})

    with pytest.raises(ValueError, match="already exists"):
        await import_statement(3, "income", 2024, "ABC", db)
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_finish_attempt_ignores_missing_row_and_truncates_errors():
    db = fake_db()
    db.get.return_value = None
    await _finish_attempt(1, db, status="failed", error="ignored")
    db.commit.assert_not_awaited()

    attempt = SimpleNamespace()
    db.get.return_value = attempt
    error = "x" * 3000
    await _finish_attempt(2, db, status="failed", statement_id=4, source_url="url", error=error)
    assert attempt.status == "failed"
    assert attempt.financial_statement_id == 4
    assert attempt.source_url == "url"
    assert len(attempt.error_message) == 2048
    assert attempt.completed_at is not None
    db.commit.assert_awaited_once()
