import pandas as pd
import pytest

from backend.app.financial_statements.financial_statement_crud import (
    YFinanceFetchError,
    _fetch_statement_sync,
)

MODULE = "backend.app.financial_statements.financial_statement_crud"


def test_fetches_curated_income_metrics_and_provenance(mocker):
    stock = mocker.Mock()
    stock.income_stmt = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [1000.0, 220.0, 150.0, 120.0]},
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
    )
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=stock)

    result = _fetch_statement_sync("TEST", "income", 2023)

    assert result["total_revenue"] == 1000.0
    assert result["operating_income"] == 150.0
    assert result["net_income"] == 120.0
    assert result["_period_end_date"].isoformat() == "2023-12-31"
    assert result["_source_provider"] == "yfinance"


def test_fetches_cash_flow_metrics(mocker):
    stock = mocker.Mock()
    stock.cashflow = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [300.0, -80.0, 220.0]},
        index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"],
    )
    mocker.patch(f"{MODULE}.yf.Ticker", return_value=stock)

    result = _fetch_statement_sync("TEST", "cash_flow", 2023)

    assert result["operating_cash_flow"] == 300.0
    assert result["capital_expenditure"] == -80.0
    assert result["free_cash_flow"] == 220.0


def test_wraps_provider_failure(mocker):
    mocker.patch(f"{MODULE}.yf.Ticker", side_effect=ConnectionError("offline"))

    with pytest.raises(YFinanceFetchError, match="Failed to fetch income statement"):
        _fetch_statement_sync("TEST", "income", 2023)
