from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.user_lifecycle import account_lifecycle_registry as registry
from backend.mystic_auth.user_lifecycle.account_lifecycle_events import (
    AccountLifecycleEvent,
    build_account_lifecycle_event,
    deliver_account_lifecycle_event,
    queue_account_lifecycle_event,
)

MODULE = "backend.mystic_auth.user_lifecycle.account_lifecycle_events"
TASK_DEFER = "backend.mystic_auth.procrastinate_tasks.account_lifecycle_tasks.deliver_account_lifecycle_event_task.defer_async"
DATABASE_ASYNC_SESSION = "backend.mystic_auth.database.connection.database.async_session"


@pytest.fixture(autouse=True)
def clear_listeners():
    original = registry._listeners[:]
    registry._listeners.clear()
    yield
    registry._listeners[:] = original


def test_event_payload_round_trips_without_sensitive_fields():
    event = build_account_lifecycle_event(
        "purged", SimpleNamespace(id=4, email="user@example.com"), actor="admin@example.com", source="admin"
    )

    restored = AccountLifecycleEvent.from_payload(event.as_payload())

    assert restored == event
    assert "password" not in event.as_payload()
    assert "token" not in event.as_payload()


@pytest.mark.asyncio
async def test_listener_receives_event():
    listener = AsyncMock()
    registry.register_account_lifecycle_listener(listener)
    event = AccountLifecycleEvent(
        event_type="soft_deleted",
        user_id=4,
        user_email="user@example.com",
        actor="user@example.com",
        source="self_service",
        occurred_at=datetime.now(UTC),
    )

    await deliver_account_lifecycle_event(event)

    listener.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_listener_failure_propagates_for_worker_retry():
    listener = AsyncMock(side_effect=RuntimeError("downstream unavailable"))
    registry.register_account_lifecycle_listener(listener)
    event = AccountLifecycleEvent(
        event_type="purged",
        user_id=4,
        user_email="user@example.com",
        actor="system:grace_period_purge",
        source="scheduled_grace_period_purge",
        occurred_at=datetime.now(UTC),
    )

    with pytest.raises(RuntimeError, match="downstream unavailable"):
        await deliver_account_lifecycle_event(event)


def _fake_session_cm(fake_session):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=fake_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _event():
    return AccountLifecycleEvent(
        event_type="soft_deleted",
        user_id=4,
        user_email="user@example.com",
        actor="user@example.com",
        source="self_service",
        occurred_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_queue_defers_and_marks_queued_when_the_row_claim_succeeds(mocker):
    outbox_row = SimpleNamespace(queued_at=None)
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=outbox_row)))
    fake_session.commit = AsyncMock()
    mocker.patch(DATABASE_ASYNC_SESSION, return_value=_fake_session_cm(fake_session))
    defer_mock = mocker.patch(TASK_DEFER, new_callable=AsyncMock, return_value=123)

    job_id = await queue_account_lifecycle_event(_event(), outbox_id=1)

    assert job_id == 123
    defer_mock.assert_awaited_once()
    assert outbox_row.queued_at is not None
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_queue_skips_deferring_when_the_row_claim_fails(mocker):
    """Regression guard: SELECT ... FOR UPDATE SKIP LOCKED WHERE queued_at
    IS NULL returning no row means either a concurrent caller already holds
    the claim (e.g. the original queue call racing the periodic reconciler
    for the same outbox row) or the row is already queued/gone. Either way
    this caller must not defer a second job for the same logical event."""
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    fake_session.commit = AsyncMock()
    mocker.patch(DATABASE_ASYNC_SESSION, return_value=_fake_session_cm(fake_session))
    defer_mock = mocker.patch(TASK_DEFER, new_callable=AsyncMock)

    job_id = await queue_account_lifecycle_event(_event(), outbox_id=1)

    assert job_id is None
    defer_mock.assert_not_awaited()
    fake_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_leaves_queued_at_unset_when_defer_fails(mocker):
    """If the claim succeeds but defer_async itself fails (queue
    unavailable), queued_at must stay NULL so the periodic reconciler can
    retry this row later, exactly like the pre-fix behavior."""
    outbox_row = SimpleNamespace(queued_at=None)
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=outbox_row)))
    fake_session.commit = AsyncMock()
    mocker.patch(DATABASE_ASYNC_SESSION, return_value=_fake_session_cm(fake_session))
    mocker.patch(
        TASK_DEFER,
        new_callable=AsyncMock,
        side_effect=RuntimeError("queue unavailable"),
    )

    job_id = await queue_account_lifecycle_event(_event(), outbox_id=1)

    assert job_id is None
    assert outbox_row.queued_at is None
    fake_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_without_outbox_id_defers_the_payload(mocker):
    defer_mock = mocker.patch(TASK_DEFER, new_callable=AsyncMock, return_value=456)
    event = _event()

    job_id = await queue_account_lifecycle_event(event)

    assert job_id == 456
    defer_mock.assert_awaited_once_with(event=event.as_payload(), outbox_id=None)


@pytest.mark.asyncio
async def test_queue_without_outbox_id_returns_none_when_queue_is_unavailable(mocker):
    mocker.patch(TASK_DEFER, new_callable=AsyncMock, side_effect=RuntimeError("queue down"))

    assert await queue_account_lifecycle_event(_event()) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_delivered_at", [None, datetime.now(UTC)])
async def test_mark_delivered_updates_only_an_undelivered_row(mocker, existing_delivered_at):
    row = SimpleNamespace(delivered_at=existing_delivered_at)
    session = MagicMock()
    session.get = AsyncMock(return_value=row)
    session.commit = AsyncMock()
    mocker.patch(DATABASE_ASYNC_SESSION, return_value=_fake_session_cm(session))

    from backend.mystic_auth.user_lifecycle.account_lifecycle_events import (
        mark_account_lifecycle_event_delivered,
    )

    await mark_account_lifecycle_event_delivered(9)

    session.get.assert_awaited_once()
    if existing_delivered_at is None:
        assert row.delivered_at is not None
        session.commit.assert_awaited_once()
    else:
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_delivered_ignores_a_missing_row(mocker):
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    mocker.patch(DATABASE_ASYNC_SESSION, return_value=_fake_session_cm(session))

    from backend.mystic_auth.user_lifecycle.account_lifecycle_events import (
        mark_account_lifecycle_event_delivered,
    )

    await mark_account_lifecycle_event_delivered(10)

    session.commit.assert_not_awaited()
