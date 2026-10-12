import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.user_session.session_events import (
    acquire_session_event_lease,
    publish_session_revoked,
    release_session_event_lease,
    session_event_stream,
    signal_shutdown,
)

MODULE = "backend.mystic_auth.user_session.session_events"


@pytest.mark.asyncio
async def test_session_event_lease_is_atomic_and_released_by_token(mocker):
    eval_mock = mocker.patch(f"{MODULE}.valkey_client.eval", new_callable=AsyncMock, return_value=1)

    token = await acquire_session_event_lease("lease@example.com", "127.0.0.1")
    assert token
    await release_session_event_lease("lease@example.com", "127.0.0.1", token)

    assert eval_mock.await_count == 2
    acquire_args = eval_mock.await_args_list[0].args
    release_args = eval_mock.await_args_list[1].args
    assert acquire_args[0].startswith("\nlocal now")
    assert acquire_args[1] == 2
    assert acquire_args[2] != acquire_args[3]
    assert release_args[1] == 2
    assert release_args[2] == acquire_args[2]
    assert release_args[3] == acquire_args[3]
    assert release_args[4] == token


@pytest.fixture(autouse=True)
def _reset_shutdown_event():
    """_shutdown_event is a module-level singleton (see main.py's lifespan
    for why it has to be), so a test that calls signal_shutdown() would
    otherwise leave every later test's stream seeing an already-shut-down
    process. Replaced (not just .clear()'d) before and after every test in
    this file: pytest-asyncio gives each test its own event loop, and
    asyncio.Event binds to whichever loop first calls .wait() on it - a
    single Event instance reused across tests raises "bound to a different
    event loop" the moment a second test's loop touches it. A fresh
    instance lets session_event_stream() (which looks the module-level name
    up fresh on every access) bind cleanly to whichever loop the current
    test is running on."""
    import backend.mystic_auth.user_session.session_events as module

    module._shutdown_event = asyncio.Event()
    yield
    module._shutdown_event = asyncio.Event()


@pytest.mark.asyncio
async def test_publish_session_revoked_publishes_to_the_users_own_channel(mocker):
    publish_mock = mocker.patch(f"{MODULE}.valkey_client.publish", new_callable=AsyncMock)

    await publish_session_revoked("user@example.com")

    publish_mock.assert_awaited_once()
    args, _ = publish_mock.call_args
    assert args[0] == "session_events:user@example.com"
    assert json.loads(args[1]) == {"type": "revoked"}


@pytest.mark.asyncio
async def test_publish_session_revoked_scopes_the_channel_per_email(mocker):
    publish_mock = mocker.patch(f"{MODULE}.valkey_client.publish", new_callable=AsyncMock)

    await publish_session_revoked("someone-else@example.com")

    args, _ = publish_mock.call_args
    assert args[0] == "session_events:someone-else@example.com"


@pytest.mark.asyncio
async def test_publish_session_revoked_swallows_valkey_errors(mocker):
    """Must never raise: a Valkey hiccup on this best-effort side-channel
    must never turn a successful revoke into a failed request, same
    reasoning as audit logging and the Manage Sessions mirror."""
    mocker.patch(f"{MODULE}.valkey_client.publish", new_callable=AsyncMock, side_effect=Exception("boom"))

    await publish_session_revoked("user@example.com")


# ---------------------------- session_event_stream ----------------------------
# Against real Valkey Pub/Sub (no mocking of valkey_client here): the whole
# point of these is proving the generator actually subscribes and reacts to
# a genuinely concurrent publish, not just that it calls the right mocked
# methods. See test_manage_sessions_integration.py's own comment for why
# this - not a full HTTP round trip through the SSE endpoint - is where
# that behavior is actually exercised.

@pytest.mark.asyncio
async def test_session_event_stream_yields_a_published_event():
    stream = session_event_stream("stream-test@example.com")

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
    stream = session_event_stream("stream-test-2@example.com")

    async def publish_to_someone_else():
        await asyncio.sleep(0.1)
        await publish_session_revoked("someone-else@example.com")

    publish_task = asyncio.create_task(publish_to_someone_else())
    try:
        # Bounded by a timeout, not a disconnect flag: session_event_stream
        # deliberately never polls for disconnection itself (see its own
        # docstring), it only ever stops when its caller closes the
        # generator - a real client disconnect ends the loop via the ASGI
        # server calling aclose() on it, exactly like the explicit aclose()
        # below.
        lines = []
        async with asyncio.timeout(0.3):
            async for line in stream:
                lines.append(line)
    except TimeoutError:
        pass
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
    stream = session_event_stream("idle-user@example.com")

    try:
        first_line = await anext(stream)
    finally:
        await stream.aclose()

    assert first_line == ": heartbeat\n\n"


@pytest.mark.asyncio
async def test_session_event_stream_unsubscribes_cleanly_on_aclose(mocker):
    """A real client disconnect reaches this generator as the ASGI server
    closing it (StreamingResponse calls aclose() on the iterator it's
    holding), not as an is_disconnected() poll inside the loop - see
    session_event_stream's own docstring for why that check was removed.
    This pins that an explicit aclose() during the heartbeat wait tears
    down the Valkey subscription cleanly (no hang, no error) and the
    generator is done afterwards."""
    mocker.patch(f"{MODULE}._HEARTBEAT_SECONDS", 0.05)
    stream = session_event_stream("disconnect-test@example.com")

    await anext(stream)  # first heartbeat: proves the subscription is live
    await stream.aclose()

    with pytest.raises(StopAsyncIteration):
        await anext(stream)


# ------------------------ graceful shutdown / connection cutoff ------------------------
# Regression coverage for the SSE drain hang: a live session_event_stream()
# used to never end on its own, so a SIGTERM/reload had nothing to wait for
# except the client disconnecting - which, for a still-open tab, is forever.
# See session_events.py's own module comments and main.py's lifespan/signal
# relay for the full mechanism these pin.

@pytest.mark.asyncio
async def test_session_event_stream_ends_promptly_when_shutdown_is_signaled():
    """The whole point of _shutdown_event: a live stream must notice a
    shutdown almost immediately, not after its next multi-second heartbeat
    timeout - that wait is what turned a graceful shutdown into a hang."""
    stream = session_event_stream("shutdown-test@example.com")
    await anext(stream)  # first heartbeat: subscription is live

    signal_shutdown()

    start = asyncio.get_event_loop().time()
    with pytest.raises(StopAsyncIteration):
        async with asyncio.timeout(1):
            await anext(stream)
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 1, "stream did not end promptly after signal_shutdown()"


@pytest.mark.asyncio
async def test_session_event_stream_shutdown_does_not_swallow_a_pending_event(mocker):
    """The shutdown path races get_message() against the shutdown signal
    (see the module's asyncio.wait call). This pins that when a real event
    is already available, it's still delivered rather than being silently
    dropped in favor of an unrelated shutdown that happens to land in the
    same instant - the fix must not trade the old bug (losing events during
    reconnect) for a new way to lose them."""
    mocker.patch(f"{MODULE}._HEARTBEAT_SECONDS", 5)
    stream = session_event_stream("shutdown-race-test@example.com")
    await anext(stream)  # first heartbeat: subscription is live

    await publish_session_revoked("shutdown-race-test@example.com")
    await asyncio.sleep(0.1)  # let the publish actually land in Valkey
    signal_shutdown()

    try:
        line = await anext(stream)
    finally:
        await stream.aclose()

    assert line.startswith("data:")
    assert json.loads(line[len("data:"):].strip()) == {"type": "revoked"}


@pytest.mark.asyncio
async def test_session_event_stream_ends_cleanly_at_the_max_connection_deadline(mocker):
    """Bounds how long any one connection is held open, independent of
    shutdown: past _MAX_CONNECTION_SECONDS the generator just returns, which
    StreamingResponse turns into a normal end-of-response - the client's
    EventSource reconnects on its own (see useSessionEventsStream.ts)."""
    mocker.patch(f"{MODULE}._MAX_CONNECTION_SECONDS", 0.05)
    mocker.patch(f"{MODULE}._HEARTBEAT_SECONDS", 20)  # would hang for 20s if the deadline check didn't fire first
    stream = session_event_stream("max-age-test@example.com")

    # `async for` swallows StopAsyncIteration by design (that's how a
    # generator signals its own natural end) - so the assertion here is
    # simply that the loop below returns well inside the 1s bound rather
    # than the timeout firing, not that anything gets raised.
    async with asyncio.timeout(1):
        async for _ in stream:
            pass


@pytest.mark.asyncio
async def test_session_event_stream_unsubscribes_cleanly_on_shutdown():
    """Same guarantee as the aclose() case above: a shutdown-triggered end
    must still tear down the Valkey subscription (no leaked pubsub
    connections across a rolling restart's worth of shutdowns)."""
    stream = session_event_stream("shutdown-cleanup-test@example.com")
    await anext(stream)  # first heartbeat: subscription is live

    signal_shutdown()
    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    # A fresh shutdown state, exactly like the fixture gives every new test:
    # signal_shutdown() above is process-wide, so leaving it set would make
    # any new stream end immediately regardless of whether the first one's
    # cleanup actually ran - not what this is pinning.
    import backend.mystic_auth.user_session.session_events as module

    module._shutdown_event = asyncio.Event()

    # A second stream on the same channel must be able to subscribe cleanly -
    # proves the first one's pubsub.unsubscribe()/aclose() actually ran.
    other_stream = session_event_stream("shutdown-cleanup-test@example.com")
    try:
        first_line = await anext(other_stream)
        assert first_line  # got a heartbeat/message, subscription is live
    finally:
        await other_stream.aclose()
