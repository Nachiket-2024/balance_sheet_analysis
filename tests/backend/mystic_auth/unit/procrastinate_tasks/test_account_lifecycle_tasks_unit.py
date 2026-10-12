from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.procrastinate_tasks import account_lifecycle_tasks as module


def _session_context(session):
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


def _row(row_id: int = 7):
    return SimpleNamespace(
        id=row_id,
        event_type="purged",
        user_id=42,
        user_email="user@example.com",
        actor="system:grace_period_purge",
        source="scheduled_grace_period_purge",
        occurred_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_delivery_task_notifies_listener_and_marks_outbox_delivered(mocker):
    deliver_mock = mocker.patch(f"{module.__name__}.deliver_account_lifecycle_event", new_callable=AsyncMock)
    mark_mock = mocker.patch(
        f"{module.__name__}.mark_account_lifecycle_event_delivered", new_callable=AsyncMock
    )
    event = {
        "event_type": "soft_deleted",
        "user_id": 42,
        "user_email": "user@example.com",
        "actor": "user@example.com",
        "source": "self_service",
        "occurred_at": datetime.now(UTC).isoformat(),
    }

    await module.deliver_account_lifecycle_event_task(event=event, outbox_id=9)

    deliver_mock.assert_awaited_once()
    assert deliver_mock.await_args.args[0].event_type == "soft_deleted"
    mark_mock.assert_awaited_once_with(9)


@pytest.mark.asyncio
async def test_delivery_task_skips_delivery_mark_when_event_is_not_from_outbox(mocker):
    deliver_mock = mocker.patch(f"{module.__name__}.deliver_account_lifecycle_event", new_callable=AsyncMock)
    mark_mock = mocker.patch(
        f"{module.__name__}.mark_account_lifecycle_event_delivered", new_callable=AsyncMock
    )
    event = {
        "event_type": "reactivated",
        "user_id": None,
        "user_email": "user@example.com",
        "actor": "admin@example.com",
        "source": "admin",
        "occurred_at": datetime.now(UTC).isoformat(),
    }

    await module.deliver_account_lifecycle_event_task(event=event)

    deliver_mock.assert_awaited_once()
    mark_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_requeues_only_rows_that_are_successfully_deferred(mocker):
    rows = [_row(7), _row(8)]
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    mocker.patch(f"{module.__name__}.database.async_session", return_value=_session_context(session))
    queue_mock = mocker.patch(
        f"{module.__name__}.queue_account_lifecycle_event",
        new_callable=AsyncMock,
        side_effect=[101, None],
    )

    assert await module.dispatch_pending_account_lifecycle_events(timestamp=0) == 1

    assert queue_mock.await_count == 2
    first_event = queue_mock.await_args_list[0].args[0]
    assert first_event.event_type == "purged"
    assert queue_mock.await_args_list[0].kwargs == {"outbox_id": 7}
    assert queue_mock.await_args_list[1].kwargs == {"outbox_id": 8}
