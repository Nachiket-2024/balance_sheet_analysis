import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.user_session.session_events import (
    acquire_session_event_lease,
    publish_permissions_changed,
    publish_session_created,
    release_session_event_lease,
    session_event_stream,
    signal_shutdown,
)

MODULE = "backend.mystic_auth.user_session.session_events"


@pytest.fixture(autouse=True)
def _reset_shutdown_event():
    import backend.mystic_auth.user_session.session_events as module

    module._shutdown_event = asyncio.Event()
    yield
    module._shutdown_event = asyncio.Event()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("publisher", "event_type"),
    [(publish_session_created, "created"), (publish_permissions_changed, "permissions_changed")],
)
async def test_publishers_send_the_expected_event(mocker, publisher, event_type):
    publish_mock = mocker.patch(f"{MODULE}.valkey_client.publish", new_callable=AsyncMock)

    await publisher("user@example.com")

    publish_mock.assert_awaited_once()
    channel, payload = publish_mock.await_args.args
    assert channel == "session_events:user@example.com"
    assert json.loads(payload) == {"type": event_type}


@pytest.mark.asyncio
@pytest.mark.parametrize("publisher", [publish_session_created, publish_permissions_changed])
async def test_publishers_swallow_valkey_errors(mocker, publisher):
    mocker.patch(f"{MODULE}.valkey_client.publish", new_callable=AsyncMock, side_effect=RuntimeError("down"))

    await publisher("user@example.com")


@pytest.mark.asyncio
async def test_acquire_lease_fails_closed_when_valkey_is_unavailable(mocker):
    mocker.patch(f"{MODULE}.valkey_client.eval", new_callable=AsyncMock, side_effect=RuntimeError("down"))

    assert await acquire_session_event_lease("user@example.com", "127.0.0.1") is None


@pytest.mark.asyncio
async def test_acquire_lease_returns_none_when_capacity_is_exhausted(mocker):
    mocker.patch(f"{MODULE}.valkey_client.eval", new_callable=AsyncMock, return_value=0)

    assert await acquire_session_event_lease("user@example.com", "127.0.0.1") is None


@pytest.mark.asyncio
async def test_release_lease_swallow_valkey_errors(mocker):
    mocker.patch(f"{MODULE}.valkey_client.eval", new_callable=AsyncMock, side_effect=RuntimeError("down"))

    await release_session_event_lease("user@example.com", "127.0.0.1", "token")


@pytest.mark.asyncio
async def test_stream_returns_when_it_cannot_acquire_a_lease(mocker):
    mocker.patch(f"{MODULE}.acquire_session_event_lease", new_callable=AsyncMock, return_value=None)
    alert_mock = mocker.patch(f"{MODULE}.capture_security_alert", new_callable=AsyncMock)

    stream = session_event_stream("user@example.com", client_ip="127.0.0.1")
    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    alert_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_returns_when_access_token_is_invalid(mocker):
    mocker.patch(f"{MODULE}._HEARTBEAT_SECONDS", 0.01)
    mocker.patch(f"{MODULE}.jwt_service.verify_token", new_callable=AsyncMock, return_value=None)
    pubsub = mocker.MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.get_message = AsyncMock(side_effect=[None, None])
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    mocker.patch(f"{MODULE}.valkey_client.pubsub", return_value=pubsub)

    stream = session_event_stream("user@example.com", lease_token="owned", access_token="expired")
    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    pubsub.unsubscribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_delivers_a_buffered_message_before_shutdown(mocker):
    pubsub = mocker.MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.get_message = AsyncMock(return_value={"data": json.dumps({"type": "revoked"})})
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    mocker.patch(f"{MODULE}.valkey_client.pubsub", return_value=pubsub)

    stream = session_event_stream("user@example.com", lease_token="owned")
    try:
        assert await anext(stream) == 'data: {"type": "revoked"}\n\n'
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_stream_logs_unexpected_pubsub_errors_and_cleans_up(mocker):
    pubsub = mocker.MagicMock()
    pubsub.subscribe = AsyncMock(side_effect=RuntimeError("broken"))
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    mocker.patch(f"{MODULE}.valkey_client.pubsub", return_value=pubsub)
    warning_mock = mocker.patch(f"{MODULE}.logger.warning")

    stream = session_event_stream("user@example.com", lease_token="owned")
    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    warning_mock.assert_called_once()
    pubsub.unsubscribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_shutdown_wins_when_waiting_for_a_message(mocker):
    mocker.patch(f"{MODULE}._HEARTBEAT_SECONDS", 5)
    pubsub = mocker.MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.get_message = AsyncMock(side_effect=[None, None])
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    mocker.patch(f"{MODULE}.valkey_client.pubsub", return_value=pubsub)

    stream = session_event_stream("user@example.com", lease_token="owned")
    await anext(stream)
    signal_shutdown()

    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    await stream.aclose()
