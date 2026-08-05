# tests/backend/app/companies/test_company_ticker_lookup_unit.py
#
# Unit coverage for company_crud.py's yfinance ticker-name lookup, mirroring
# balance_sheets' own test_balance_sheet_crud_unit.py pattern: mock yfinance
# rather than hit the network, no HTTP client needed since there's no DB
# interaction on this path.
import pytest
from backend.app.companies.company_crud import (
    TickerLookupError,
    _lookup_company_name_by_ticker_sync,
    lookup_company_name_by_ticker,
)

MODULE = "backend.app.companies.company_crud"


def test_lookup_returns_long_name_when_present(mocker):
    mocker.patch(f"{MODULE}.yf.Ticker").return_value.info = {"longName": "Apple Inc.", "shortName": "Apple"}

    assert _lookup_company_name_by_ticker_sync("AAPL") == "Apple Inc."


def test_lookup_falls_back_to_short_name(mocker):
    mocker.patch(f"{MODULE}.yf.Ticker").return_value.info = {"shortName": "Apple"}

    assert _lookup_company_name_by_ticker_sync("AAPL") == "Apple"


def test_lookup_returns_none_for_an_unknown_ticker(mocker):
    """A typo'd/delisted ticker is a normal "nothing found" outcome, not an
    error: yfinance still returns a (near-empty) info dict for it."""
    mocker.patch(f"{MODULE}.yf.Ticker").return_value.info = {}

    assert _lookup_company_name_by_ticker_sync("NOPE") is None


def test_lookup_wraps_yfinance_failures_as_ticker_lookup_error(mocker):
    mocker.patch(f"{MODULE}.yf.Ticker", side_effect=ConnectionError("network unreachable"))

    with pytest.raises(TickerLookupError, match="Failed to look up ticker"):
        _lookup_company_name_by_ticker_sync("AAPL")


@pytest.mark.asyncio
async def test_async_wrapper_delegates_to_thread(mocker):
    mocker.patch(f"{MODULE}._lookup_company_name_by_ticker_sync", return_value="Apple Inc.")

    assert await lookup_company_name_by_ticker("AAPL") == "Apple Inc."
