# tests/backend/app/companies/test_company_ticker_search_unit.py
#
# Unit coverage for company_crud.py's yfinance ticker-search autocomplete,
# mirroring test_company_ticker_lookup_unit.py's pattern: mock yfinance
# rather than hit the network.
import pytest

from backend.app.companies.company_crud import (
    TickerLookupError,
    _search_company_tickers_sync,
    search_company_tickers,
)

MODULE = "backend.app.companies.company_crud"


def test_search_maps_quotes_to_results(mocker):
    mocker.patch(f"{MODULE}.yf.Search").return_value.quotes = [
        {"symbol": "MSFT", "longname": "Microsoft Corporation", "exchDisp": "NMS"},
        {"symbol": "GITHUB.DEMO", "shortname": "GitHub, Inc.", "exchange": "DEMO"},
    ]

    results = _search_company_tickers_sync("REL")

    assert results == [
        {"ticker": "MSFT", "name": "Microsoft Corporation", "exchange": "NMS"},
        {"ticker": "GITHUB.DEMO", "name": "GitHub, Inc.", "exchange": "DEMO"},
    ]


def test_search_skips_quotes_missing_symbol_or_name(mocker):
    mocker.patch(f"{MODULE}.yf.Search").return_value.quotes = [
        {"symbol": "RS"},
        {"longname": "No Symbol Co"},
        {"symbol": "OK", "longname": "Okay Co"},
    ]

    results = _search_company_tickers_sync("REL")

    assert results == [{"ticker": "OK", "name": "Okay Co", "exchange": ""}]


def test_search_wraps_yfinance_failures_as_ticker_lookup_error(mocker):
    mocker.patch(f"{MODULE}.yf.Search", side_effect=ConnectionError("network unreachable"))

    with pytest.raises(TickerLookupError, match="Failed to search tickers"):
        _search_company_tickers_sync("REL")


@pytest.mark.asyncio
async def test_async_wrapper_delegates_to_thread(mocker):
    mocker.patch(f"{MODULE}._search_company_tickers_sync", return_value=[{"ticker": "GITHUB.DEMO", "name": "GitHub, Inc.", "exchange": "DEMO"}])

    assert await search_company_tickers("GIT") == [{"ticker": "GITHUB.DEMO", "name": "GitHub, Inc.", "exchange": "DEMO"}]
