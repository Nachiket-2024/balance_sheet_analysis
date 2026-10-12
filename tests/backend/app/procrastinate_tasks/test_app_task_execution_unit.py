from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.procrastinate_tasks import (
    analysis_notification_tasks,
    financial_refresh_tasks,
)


class Result:
    def __init__(self, *, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.scalar


def session_context(session):
    @asynccontextmanager
    async def context():
        yield session

    return context()


@pytest.mark.asyncio
async def test_financial_refresh_refreshes_each_latest_period(mocker):
    company = SimpleNamespace(id=9, ticker="EXAMPLE")
    balance = SimpleNamespace(company_id=9, year=2024)
    statements = [
        SimpleNamespace(statement_type="income", year=2024, period_type="annual", period_number=0),
        SimpleNamespace(statement_type="cash_flow", year=2024, period_type="quarterly", period_number=2),
    ]
    db = SimpleNamespace(execute=AsyncMock(side_effect=[Result(rows=[company]), Result(scalar=balance), Result(rows=statements)]))
    mocker.patch.object(financial_refresh_tasks.database, "async_session", return_value=session_context(db))
    balance_refresh = mocker.patch.object(financial_refresh_tasks, "import_balance_sheet", new_callable=AsyncMock)
    statement_refresh = mocker.patch.object(financial_refresh_tasks, "import_statement", new_callable=AsyncMock)

    refreshed = await financial_refresh_tasks.refresh_latest_financial_periods.func(123)

    assert refreshed == 3
    balance_refresh.assert_awaited_once_with(9, 2024, "EXAMPLE", db, refresh=True)
    assert statement_refresh.await_count == 2
    assert statement_refresh.await_args_list[1].kwargs == {
        "refresh": True,
        "period_type": "quarterly",
        "period_number": 2,
    }


@pytest.mark.asyncio
async def test_financial_refresh_counts_provider_failures_and_continues(mocker):
    company = SimpleNamespace(id=9, ticker="EXAMPLE")
    balance = SimpleNamespace(company_id=9, year=2024)
    statement = SimpleNamespace(statement_type="income", year=2024, period_type="annual", period_number=0)
    db = SimpleNamespace(execute=AsyncMock(side_effect=[Result(rows=[company]), Result(scalar=balance), Result(rows=[statement])]))
    mocker.patch.object(financial_refresh_tasks.database, "async_session", return_value=session_context(db))
    balance_refresh = mocker.patch.object(financial_refresh_tasks, "import_balance_sheet", new_callable=AsyncMock, side_effect=RuntimeError("provider down"))
    statement_refresh = mocker.patch.object(financial_refresh_tasks, "import_statement", new_callable=AsyncMock, side_effect=RuntimeError("provider down"))

    with pytest.raises(RuntimeError, match="2 provider failure"):
        await financial_refresh_tasks.refresh_latest_financial_periods.func(123)
    balance_refresh.assert_awaited_once()
    statement_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_financial_refresh_empty_company_list_returns_zero(mocker):
    db = SimpleNamespace(execute=AsyncMock(return_value=Result(rows=[])))
    mocker.patch.object(financial_refresh_tasks.database, "async_session", return_value=session_context(db))
    assert await financial_refresh_tasks.refresh_latest_financial_periods.func(123) == 0


@pytest.mark.asyncio
async def test_notification_task_queues_email_and_marks_successful_webhook(mocker):
    alert = SimpleNamespace(company_id=9, message="Cash warning", years=[2024])
    policy = SimpleNamespace(enabled=True)
    delivery = SimpleNamespace(recipient="owner@example.com", job_id=None)
    webhook = SimpleNamespace(status="queued")
    db = SimpleNamespace(execute=AsyncMock(return_value=Result(rows=[(alert, policy)])), commit=AsyncMock())
    mocker.patch.object(analysis_notification_tasks.database, "async_session", return_value=session_context(db))
    mocker.patch.object(analysis_notification_tasks, "queue_alert_deliveries", new_callable=AsyncMock, return_value=[delivery])
    mocker.patch.object(analysis_notification_tasks, "get_or_create_webhook_delivery", new_callable=AsyncMock, return_value=webhook)
    mocker.patch.object(analysis_notification_tasks, "deliver_webhook", new_callable=AsyncMock, return_value=True)
    defer = mocker.patch.object(analysis_notification_tasks.send_email_task, "defer_async", new_callable=AsyncMock, return_value=44)

    queued = await analysis_notification_tasks.queue_analysis_alert_notifications.func(123)

    assert queued == 2
    assert delivery.job_id == 44
    assert webhook.status == "sent"
    assert defer.await_args.kwargs["to_email"] == "owner@example.com"
    assert "2024" in defer.await_args.kwargs["body"]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_notification_task_keeps_failed_webhook_for_retry_and_skips_sent(mocker):
    alert = SimpleNamespace(company_id=9, message="Cash warning", years=[])
    policy = SimpleNamespace(enabled=True)
    failed_webhook = SimpleNamespace(status="failed")
    sent_webhook = SimpleNamespace(status="sent")
    db = SimpleNamespace(execute=AsyncMock(return_value=Result(rows=[(alert, policy), (alert, policy)])), commit=AsyncMock())
    mocker.patch.object(analysis_notification_tasks.database, "async_session", return_value=session_context(db))
    mocker.patch.object(analysis_notification_tasks, "queue_alert_deliveries", new_callable=AsyncMock, return_value=[])
    mocker.patch.object(analysis_notification_tasks, "get_or_create_webhook_delivery", new_callable=AsyncMock, side_effect=[failed_webhook, sent_webhook])
    mocker.patch.object(analysis_notification_tasks, "deliver_webhook", new_callable=AsyncMock, return_value=False)

    assert await analysis_notification_tasks.queue_analysis_alert_notifications.func(123) == 0
    assert failed_webhook.status == "failed"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_notification_task_leaves_rows_alone_when_there_is_no_delivery(mocker):
    alert = SimpleNamespace(company_id=9, message="No recipients", years=[])
    policy = SimpleNamespace(enabled=False)
    db = SimpleNamespace(execute=AsyncMock(return_value=Result(rows=[(alert, policy)])), commit=AsyncMock())
    mocker.patch.object(analysis_notification_tasks.database, "async_session", return_value=session_context(db))
    mocker.patch.object(analysis_notification_tasks, "queue_alert_deliveries", new_callable=AsyncMock, return_value=[])
    mocker.patch.object(analysis_notification_tasks, "get_or_create_webhook_delivery", new_callable=AsyncMock, return_value=None)

    assert await analysis_notification_tasks.queue_analysis_alert_notifications.func(123) == 0
    db.commit.assert_not_awaited()
