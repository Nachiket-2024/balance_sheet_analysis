from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from backend.app.api.llm_routes import llm_routes as routes
from backend.app.llm.llm_schema import ChatRequest


async def passthrough(value, *_args, **_kwargs):
    return await value if hasattr(value, "__await__") else value


@pytest.mark.asyncio
async def test_provider_status_persists_probe_and_expires_old_probes(mocker):
    db = SimpleNamespace(add=Mock(), execute=AsyncMock(), commit=AsyncMock())
    checked_at = datetime.now(UTC)
    mocker.patch.object(routes, "probe_provider", new_callable=AsyncMock, return_value=(False, 12.5, "offline", checked_at))

    result = await routes.provider_status({"email": "user@example.com"}, db)

    assert result.reachable is False
    assert result.error_code == "offline"
    assert db.add.call_args.args[0].checked_at == checked_at
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_summary_reports_daily_totals():
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one=lambda: (3, 745))))
    summary = await routes.usage_summary({"email": "user@example.com"}, db)
    assert summary.requests == 3
    assert summary.characters_used == 745


@pytest.mark.asyncio
async def test_chat_enforces_budget_records_success_and_maps_provider_error(mocker):
    user = {"email": "user@example.com"}
    db = SimpleNamespace(add=Mock(), commit=AsyncMock())
    company = SimpleNamespace(id=7, name="Example Co", ticker="EX", group_root_id=None)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company)
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=passthrough)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    mocker.patch.object(routes, "list_balance_sheets_for_company_years", new_callable=AsyncMock, return_value=[])
    mocker.patch.object(routes, "calculate_analysis", return_value=object())
    mocker.patch.object(routes, "analysis_context", return_value="grounded")
    mocker.patch.object(routes, "list_statements", new_callable=AsyncMock, return_value=[])
    mocker.patch.object(routes, "build_statement_context", return_value="statement context")
    mocker.patch.object(routes, "daily_usage_chars", new_callable=AsyncMock, return_value=100)
    mocker.patch.object(routes, "has_budget", return_value=True)
    mocker.patch.object(routes, "ask_groq", new_callable=AsyncMock, return_value="Answer")
    payload = ChatRequest(company_id=7, years=[2024], question="What changed?")

    response = await routes.chat(object(), payload, user, db)
    assert response.answer == "Answer"
    assert db.add.call_args.args[0].status == "success"
    db.commit.assert_awaited_once()

    mocker.patch.object(routes, "has_budget", return_value=False)
    with pytest.raises(HTTPException) as error:
        await routes.chat(object(), payload, user, db)
    assert error.value.status_code == 429

    mocker.patch.object(routes, "has_budget", return_value=True)
    mocker.patch.object(routes, "ask_groq", new_callable=AsyncMock, side_effect=RuntimeError("provider down"))
    with pytest.raises(HTTPException) as error:
        await routes.chat(object(), payload, user, db)
    assert error.value.status_code == 502
    assert db.add.call_args.args[0].error_code == "RuntimeError"


@pytest.mark.asyncio
async def test_feedback_saves_user_attributed_rating(mocker):
    user = {"email": "user@example.com"}
    db = SimpleNamespace(add=Mock(), commit=AsyncMock())
    company = SimpleNamespace(id=5, group_root_id=None)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company)
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=passthrough)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)

    result = await routes.feedback(SimpleNamespace(helpful=False, comment="Not grounded"), 5, user, db)
    assert result == {"recorded": True}
    assert db.add.call_args.args[0].user_email == user["email"]
    assert db.add.call_args.args[0].helpful is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_usage_and_provider_operations_aggregate_rows(mocker):
    user = {"email": "admin@example.com"}
    auth = mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)

    class UsageResult:
        def all(self):
            return [("a@example.com", 3, 500, 1), ("b@example.com", 2, 250, None)]

    usage_db = SimpleNamespace(execute=AsyncMock(return_value=UsageResult()))
    usage = await routes.admin_usage_summary(user, usage_db)
    assert usage.total_requests == 5
    assert usage.total_characters == 750
    assert usage.failed_requests == 1
    assert len(usage.users) == 2
    auth.assert_awaited_once()

    checked_at = datetime.now(UTC)

    class OperationsResult:
        def one(self):
            return 4, 3, 12.345, checked_at

    class ErrorResult:
        def scalar_one_or_none(self):
            return "timeout"

    operations_db = SimpleNamespace(execute=AsyncMock(side_effect=[OperationsResult(), ErrorResult()]))
    operations = await routes.admin_provider_operations(user, operations_db)
    assert operations.probes == 4
    assert operations.reachable_probes == 3
    assert operations.failed_probes == 1
    assert operations.average_latency_ms == 12.35
    assert operations.last_checked_at == checked_at
    assert operations.last_error_code == "timeout"
