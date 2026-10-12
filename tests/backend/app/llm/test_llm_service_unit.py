# tests/backend/app/llm/test_llm_service_unit.py
#
# Pure unit coverage for llm_service.ask_groq's error handling. No HTTP
# client, no DB; httpx itself is mocked so these run instantly and never
# touch the real Groq API.
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.balance_sheets.balance_sheet_model import BalanceSheet
from backend.app.financial_statements.financial_statement_model import (
    FinancialStatement,
)
from backend.app.llm import llm_service

MODULE = "backend.app.llm.llm_service"


def test_grounding_context_contains_source_metrics_and_deterministic_analysis():
    context = llm_service.build_grounding_context(
        "Example Co",
        "EXAMPLE",
        [
            BalanceSheet(company_id=1, year=2023, total_assets=100, current_assets=60, current_liabilities=40, stockholders_equity=50, total_debt=20, cash_cash_equivalents_and_short_term_investments=10, receivables=15),
        ],
    )
    assert "Company: Example Co (EXAMPLE)" in context
    assert "total_assets=100.00" in context
    assert "current_ratio" in context
    assert "cash_as_pct_assets" in context
    assert "revenue" not in context.lower()


def test_statement_context_contains_stable_citation_tokens():
    context = llm_service.build_statement_context([
        FinancialStatement(company_id=1, statement_type="income", year=2023, total_revenue=1000),
    ])

    assert "[source:income:FY2023:total_revenue]" in context
    assert "total_revenue=1,000.00" in context


def _mock_client(mocker, response=None, raise_exc=None):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=response)
    if raise_exc is not None:
        mock_client.post = AsyncMock(side_effect=raise_exc)
    else:
        mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch(f"{MODULE}.httpx.AsyncClient", return_value=mock_client)
    return mock_client


@pytest.mark.asyncio
async def test_provider_probe_checks_models_endpoint_without_completion_tokens(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    response = MagicMock(is_success=True)
    client = _mock_client(mocker, response=response)

    reachable, latency_ms, error_code, checked_at = await llm_service.probe_provider()

    assert reachable is True
    assert latency_ms is not None
    assert error_code is None
    assert checked_at.tzinfo is not None
    client.get.assert_called_once()
    assert client.get.call_args.args[0].endswith("/models")


@pytest.mark.asyncio
async def test_provider_probe_reports_unconfigured_without_network(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "")
    mocker.patch(f"{MODULE}.httpx.AsyncClient")

    reachable, latency_ms, error_code, _ = await llm_service.probe_provider()

    assert reachable is False
    assert latency_ms is None
    assert error_code == "not_configured"


@pytest.mark.asyncio
async def test_raises_when_api_key_not_configured(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "")

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not configured"):
        await llm_service.ask_groq("question", "context")


@pytest.mark.asyncio
async def test_returns_content_on_success(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": "  the answer  "}}]}
    client = _mock_client(mocker, response=response)

    answer = await llm_service.ask_groq("question", "context")

    assert answer == "the answer"
    request_payload = client.post.call_args.kwargs["json"]
    assert request_payload["max_tokens"] >= 128
    assert request_payload["temperature"] == 0
    assert "[source:...]" in request_payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_raises_on_non_200_response(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    response = MagicMock(status_code=500, text="internal error")
    _mock_client(mocker, response=response)

    with pytest.raises(RuntimeError, match="Groq API error"):
        await llm_service.ask_groq("question", "context")


@pytest.mark.asyncio
async def test_raises_on_unexpected_response_shape(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    response = MagicMock(status_code=200, text="{}")
    response.json.return_value = {}
    _mock_client(mocker, response=response)

    with pytest.raises(RuntimeError, match="Unexpected Groq API response shape"):
        await llm_service.ask_groq("question", "context")


@pytest.mark.asyncio
async def test_raises_on_network_failure(mocker):
    import httpx

    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    _mock_client(mocker, raise_exc=httpx.ConnectError("connection refused"))

    with pytest.raises(RuntimeError, match="Failed to reach Groq API"):
        await llm_service.ask_groq("question", "context")
