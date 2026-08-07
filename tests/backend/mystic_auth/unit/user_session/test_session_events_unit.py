import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.user_session.session_events import (
    publish_session_revoked,
    session_event_stream,
)

MODULE = "backend.mystic_auth.user_session.session_events"


class _FakeRequest:
    """Minimal stand-in for FastAPI's Request: session_event_stream only
    ever calls is_disconnected() on it."""

    def __init__(self):
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


@pytest.mark.asyncio
async def test_publish_session_revoked_publishes_to_the_users_own_channel(mocker):
    publish_mock = mocker.patch(f"{MODULE}.redis_client.publish", new_callable=AsyncMock)

    await publish_session_revoked("user@example.com")

    publish_mock.assert_awaited_once()
    args, _ = publish_mock.call_args
    assert args[0] == "session_events:user@example.com"
    assert json.loads(args[1]) == {"type": "revoked"}


@pytest.mark.asyncio
async def test_publish_session_revoked_scopes_the_channel_per_email(mocker):
    publish_mock = mocker.patch(f"{MODULE}.redis_client.publish", new_callable=AsyncMock)

    await publish_session_revoked("someone-else@example.com")

    args, _ = publish_mock.call_args
    assert args[0] == "session_events:someone-else@example.com"


@pytest.mark.asyncio
async def test_publish_session_revoked_swallows_redis_errors(mocker):
    """Must never raise: a Redis hiccup on this best-effort side-channel
    must never turn a successful revoke into a failed request, same
    reasoning as audit logging and the Manage Sessions mirror."""
    mocker.patch(f"{MODULE}.redis_client.publish", new_callable=AsyncMock, side_effect=Exception("boom"))

    await publish_session_revoked("user@example.com")


# ---------------------------- session_event_stream ----------------------------
# Against real Redis Pub/Sub (no mocking of redis_client here): the whole
# point of these is proving the generator actually subscribes and reacts to
# a genuinely concurrent publish, not just that it calls the right mocked
# methods. See test_manage_sessions_integration.py's own comment for why
# this - not a full HTTP round trip through the SSE endpoint - is where
# that behavior is actually exercised.

@pytest.mark.asyncio
async def test_session_event_stream_yields_a_published_event():
    request = _FakeRequest()
    stream = session_event_stream("stream-test@example.com", request)

    async def publish_soon():
        await asyncio.sleep(0.2)
        await publish_session_revoked("stream-test@example.com")

    publish_task = asyncio.create_task(publish_soon())
    try:
        received = None
        async for line in stream:
            if line.startswith("data:"):
                received = json.loads(line[len("data:"):].strip())
                break
    finally:
        await stream.aclose()
        await publish_task

    assert received == {"type": "revoked"}


@pytest.mark.asyncio
async def test_session_event_stream_ignores_a_different_users_channel(mocker):
    """Two users' streams must never cross: a publish on someone else's
    channel must never surface on this one."""
    mocker.patch(f"{MODULE}._HEARTBEAT_SECONDS", 0.05)
    request = _FakeRequest()
    stream = session_event_stream("stream-test-2@example.com", request)

    async def publish_to_someone_else():
        await asyncio.sleep(0.1)
        await publish_session_revoked("someone-else@example.com")
        await asyncio.sleep(0.2)
        request.disconnected = True

    publish_task = asyncio.create_task(publish_to_someone_else())
    try:
        lines = [line async for line in stream]
    finally:
        await stream.aclose()
        await publish_task

    assert not any(line.startswith("data:") for line in lines)


@pytest.mark.asyncio
async def test_session_event_stream_sends_heartbeats_when_idle(mocker):
    """Keeps the connection alive through idle proxies/load balancers when
    nothing has actually happened - see the module's own _HEARTBEAT_SECONDS
    comment."""
    mocker.patch(f"{MODULE}._HEARTBEAT_SECONDS", 0.05)
    request = _FakeRequest()
    stream = session_event_stream("idle-user@example.com", request)

    try:
        first_line = await anext(stream)
    finally:
        await stream.aclose()

    assert first_line == ": heartbeat\n\n"


@pytest.mark.asyncio
async def test_session_event_stream_exits_cleanly_when_client_disconnects():
    request = _FakeRequest()
    request.disconnected = True
    stream = session_event_stream("user@example.com", request)

    lines = [line async for line in stream]

    assert lines == []
