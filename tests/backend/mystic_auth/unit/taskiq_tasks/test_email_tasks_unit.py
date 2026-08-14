# tests/backend/mystic_auth/unit/test_email_tasks_unit.py
#
# Regression guard for email delivery reliability: send_email_task previously
# caught every exception and returned False, which the retry middleware
# never sees (it only reacts to a raised exception) : so a transient SMTP
# failure silently dropped the email with no retry. The fix makes the task
# raise on failure (after logging) so the middleware can schedule a
# re-enqueue, up to max_retries, while every attempt still leaves a full
# traceback in the logs.
from unittest.mock import AsyncMock, patch

import pytest
from backend.mystic_auth.taskiq_tasks.email_tasks import (
    ResilientRedisStreamBroker,
    broker,
    send_email_task,
)
from redis.exceptions import ConnectionError, ResponseError
from taskiq import SmartRetryMiddleware

MODULE = "backend.mystic_auth.taskiq_tasks.email_tasks"


@pytest.mark.asyncio
async def test_send_email_task_returns_true_on_success(mocker):
    mocker.patch(f"{MODULE}.email_sender.send", new_callable=AsyncMock)
    info_mock = mocker.patch(f"{MODULE}.logger.info")

    result = await send_email_task(to_email="user@example.com", subject="Hi", body="Body")

    assert result is True
    info_mock.assert_any_call("Sending email to %s", "user@example.com")
    info_mock.assert_any_call("Email sent successfully to %s", "user@example.com")


@pytest.mark.asyncio
async def test_send_email_task_logs_and_reraises_on_send_failure(mocker):
    mocker.patch(f"{MODULE}.email_sender.send", new_callable=AsyncMock, side_effect=RuntimeError("SMTP down"))
    error_mock = mocker.patch(f"{MODULE}.logger.error")

    with pytest.raises(RuntimeError):
        await send_email_task(to_email="user@example.com", subject="Hi", body="Body")

    error_mock.assert_called_once()


def test_broker_has_retry_middleware_configured():
    assert any(isinstance(m, SmartRetryMiddleware) for m in broker.middlewares)


def test_broker_retry_middleware_uses_backoff_schedule_source():
    retry_middleware = next(m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware))
    assert retry_middleware.schedule_source is not None
    assert retry_middleware.use_delay_exponent is True


def test_send_email_task_is_labeled_to_retry_on_error():
    assert send_email_task.labels.get("retry_on_error") is True
    assert send_email_task.labels.get("max_retries") == 3


def test_broker_uses_mkstream_for_deterministic_group_creation():
    """taskiq spawns multiple worker processes (default: 2), each independently
    calling broker.startup() on a fresh Redis instance. mkstream=True makes the
    stream + consumer group creation a single atomic XGROUP CREATE ... MKSTREAM,
    so there's no window where the stream exists but the group doesn't (or vice
    versa) for a concurrent XREADGROUP to race against."""
    assert broker.mkstream is True


@pytest.mark.asyncio
async def test_broker_startup_survives_concurrent_group_creation_race():
    """Regression guard for the fresh-Redis startup race previously documented
    in docs/mystic_auth/concerns/README.md. Every worker process calls
    broker.startup() -> XGROUP CREATE ... MKSTREAM independently; Redis raises
    BUSYGROUP for whichever process loses that race. The broker must swallow
    it (not propagate) so a losing process doesn't crash-loop."""
    with patch("taskiq_redis.redis_broker.Redis") as redis_cls:
        redis_conn = AsyncMock()
        redis_conn.xgroup_create = AsyncMock(
            side_effect=ResponseError("BUSYGROUP Consumer Group name already exists")
        )
        redis_cls.return_value.__aenter__.return_value = redis_conn

        await broker._declare_consumer_group()  # must not raise


@pytest.mark.asyncio
async def test_resilient_broker_redeclares_group_after_runtime_nogroup(mocker):
    test_broker = ResilientRedisStreamBroker(url="redis://localhost:6379/0")
    sentinel = object()
    calls = 0

    async def fake_listen(self):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ResponseError("NOGROUP No such key 'taskiq' or consumer group 'taskiq'")
        yield sentinel

    mocker.patch("taskiq_redis.redis_broker.RedisStreamBroker.listen", fake_listen)
    declare_mock = mocker.patch.object(test_broker, "_declare_consumer_group", new_callable=AsyncMock)

    listener = test_broker.listen()
    message = await anext(listener)
    await listener.aclose()

    assert message is sentinel
    declare_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_resilient_broker_reconnects_after_connection_drop(mocker):
    test_broker = ResilientRedisStreamBroker(url="redis://localhost:6379/0")
    sentinel = object()
    calls = 0

    async def fake_listen(self):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("Connection closed by server.")
        yield sentinel

    mocker.patch("taskiq_redis.redis_broker.RedisStreamBroker.listen", fake_listen)
    sleep_mock = mocker.patch(f"{MODULE}.sleep", new_callable=AsyncMock)

    listener = test_broker.listen()
    message = await anext(listener)
    await listener.aclose()

    assert message is sentinel
    sleep_mock.assert_awaited_once_with(1)
