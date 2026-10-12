import asyncio
import hashlib
import json
import time
import traceback
from collections.abc import AsyncIterator
from uuid import uuid4

from ..audit_log.audit_log_service import SESSION_EVENT_CONNECTION_LIMIT_EXCEEDED
from ..auth.token_logic.jwt_service import jwt_service
from ..core.settings import settings
from ..error_monitoring.sentry_service import capture_security_alert
from ..logging.logging_config import get_logger
from ..valkey.client import valkey_client

logger = get_logger(__name__)

_CHANNEL_TEMPLATE = "session_events:{email}"

# How often the stream sends a keep-alive comment when no real event has
# arrived, so intermediate proxies/load balancers (and the browser's own
# idle-connection timeout) don't treat a quiet-but-healthy connection as
# dead and close it.
_HEARTBEAT_SECONDS = 20

# Upper bound on how long one SSE connection stays open. Past this, the
# generator returns and the response ends normally; EventSource treats that
# like a dropped connection and reconnects on its own. Bounds how long a
# stuck client can hold a Valkey pubsub connection open, and gives a
# connection that misses the shutdown signal a ceiling too. Long enough
# that reconnects are rare, short enough to never block a deploy's
# shutdown timeout.
#
# This TTL is also the only thing bounding an *abrupt* disconnect (a
# closed laptop lid, a killed tab) rather than a clean one - worth asking
# whether that's tightenable with an active server-side probe instead. It
# deliberately isn't: see
# session_event_stream's own docstring below for why polling
# request.is_disconnected() was already tried and reverted here
# specifically (it closed live connections within milliseconds under this
# app's BaseHTTPMiddleware stack, silently dropping push events - a worse
# bug than the slow release this TTL accepts). Shortening this constant
# instead is still a reasonable, lower-risk option if a deployment's
# connection count ever makes the current 15-minute worst case matter in
# practice; nothing here makes that unsafe, there's just no evidence yet
# that it's needed.
_MAX_CONNECTION_SECONDS = 15 * 60
_LEASE_TTL_SECONDS = _MAX_CONNECTION_SECONDS + settings.SESSION_EVENT_LEASE_GRACE_SECONDS
_LEASE_KEY_PREFIX = "session_event_leases"

# Sorted sets allow expired leases to be removed atomically before admission.
# The Lua script makes cleanup, capacity checks, and both inserts one atomic
# Valkey operation across every API worker in a multi-process deployment.
_ACQUIRE_LEASE_SCRIPT = """
local now = tonumber(ARGV[1])
local expires = tonumber(ARGV[2])
local account_limit = tonumber(ARGV[3])
local ip_limit = tonumber(ARGV[4])
local token = ARGV[5]
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= account_limit then return 0 end
if redis.call('ZCARD', KEYS[2]) >= ip_limit then return 0 end
redis.call('ZADD', KEYS[1], expires, token)
redis.call('ZADD', KEYS[2], expires, token)
redis.call('EXPIRE', KEYS[1], ARGV[6])
redis.call('EXPIRE', KEYS[2], ARGV[6])
return 1
"""

_RELEASE_LEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
if redis.call('ZCARD', KEYS[1]) == 0 then redis.call('DEL', KEYS[1]) end
if redis.call('ZCARD', KEYS[2]) == 0 then redis.call('DEL', KEYS[2]) end
return 1
"""


def _lease_key(scope: str, value: str) -> str:
    """Hash identifiers before storing them as inspectable Valkey keys."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{_LEASE_KEY_PREFIX}:{scope}:{digest}"


async def acquire_session_event_lease(email: str, client_ip: str) -> str | None:
    """Reserve one globally-counted SSE slot or fail closed.

    The live-update stream is optional. If Valkey is unavailable, rejecting
    this channel avoids accepting unbounded long-lived sockets while normal
    authenticated API requests continue to use their existing failure policy.
    """
    token = uuid4().hex
    now = int(time.time())
    expires = now + _MAX_CONNECTION_SECONDS
    try:
        admitted = await valkey_client.eval(
            _ACQUIRE_LEASE_SCRIPT,
            2,
            _lease_key("account", email),
            _lease_key("ip", client_ip),
            now,
            expires,
            settings.SESSION_EVENT_MAX_CONNECTIONS_PER_ACCOUNT,
            settings.SESSION_EVENT_MAX_CONNECTIONS_PER_IP,
            token,
            _LEASE_TTL_SECONDS,
        )
    except Exception:
        logger.error("Unable to reserve session-event connection capacity:\n%s", traceback.format_exc())
        return None

    return token if int(admitted) == 1 else None


async def release_session_event_lease(email: str, client_ip: str, token: str) -> None:
    """Release only this stream's lease; expiry remains the crash recovery path."""
    try:
        await valkey_client.eval(
            _RELEASE_LEASE_SCRIPT,
            2,
            _lease_key("account", email),
            _lease_key("ip", client_ip),
            token,
        )
    except Exception:
        logger.warning("Unable to release session-event connection lease:\n%s", traceback.format_exc())

# Set from main.py's lifespan shutdown, right before it disposes the DB pool
# and closes valkey_client. Lets every open session_event_stream() loop
# notice immediately and return, instead of the ASGI server waiting on the
# next heartbeat or _MAX_CONNECTION_SECONDS. See session_event_stream's
# docstring for why polling request.is_disconnected() doesn't work here.
_shutdown_event = asyncio.Event()


def signal_shutdown() -> None:
    """Called once from main.py's lifespan teardown. Wakes every currently
    open session_event_stream() loop so it exits immediately instead of the
    process hanging past its graceful-shutdown timeout waiting for
    long-lived SSE connections to drain on their own."""
    _shutdown_event.set()


async def publish_session_revoked(email: str) -> None:
    """
    Real-time nudge: tells every open tab/device currently holding a live
    GET /auth/session-events connection for this account to re-check its
    own session right now (a normal GET /auth/me / GET /auth/sessions
    refetch), instead of waiting for its next background poll or window-
    focus refetch. Best-effort and never raises: a Valkey hiccup here must
    never turn a successful revoke into a failed request, the same
    reasoning as every other best-effort side-channel in this codebase
    (audit logging, the Manage Sessions mirror).

    Deliberately just a "something changed, go check" signal, not "you are
    logged out": the receiving tab might be a completely different,
    unaffected session (see refresh_token_service.revoke_chain_for_user),
    so the actual authoritative answer still comes from the normal
    request/response auth checks, never from this event's payload.
    """
    try:
        await valkey_client.publish(_CHANNEL_TEMPLATE.format(email=email), json.dumps({"type": "revoked"}))
    except Exception:
        logger.warning("Failed to publish session-revoked event for %s:\n%s", email, traceback.format_exc())


async def publish_session_created(email: str) -> None:
    """
    Same real-time nudge as publish_session_revoked, fired the moment a new
    login (password or OAuth2) creates a session row instead of one ending.
    Without this, a tab already open on Dashboard/Account Settings/Manage
    Sessions would only learn about a fresh login on another device via its
    own background poll (useCurrentUserQuery/useSessionsQuery's
    refetchInterval) or a window-focus refetch - "Active sessions" and
    "Manage Sessions" could sit stale for up to that interval after a login
    elsewhere, unlike a revoke, which already gets this treatment.
    """
    try:
        await valkey_client.publish(_CHANNEL_TEMPLATE.format(email=email), json.dumps({"type": "created"}))
    except Exception:
        logger.warning("Failed to publish session-created event for %s:\n%s", email, traceback.format_exc())


async def publish_permissions_changed(email: str) -> None:
    """
    Same real-time nudge as publish_session_revoked, fired the moment an
    admin grants or revokes one of this account's policies (see
    policy_assignment_routes.py). Without this, a tab this account already
    has open - e.g. sat on the Rate Limit Dashboard, which is gated on
    rate_limits:read - would keep rendering with its now-stale cached
    permissions (useCurrentUserQuery's own 2-minute refetchInterval) until
    that poll, a window-focus refetch, or a manual reload: exactly the
    "revoked access still visibly usable for a while" gap this exists to
    close. Deliberately reuses the same session_events channel/frontend
    handler as revoke/created (useSessionEventsStream already invalidates
    CURRENT_USER_QUERY_KEY on any message) rather than adding a second
    stream - the receiving tab still re-derives everything from a normal
    GET /auth/me, this is only the "something changed, go check" signal.
    """
    try:
        await valkey_client.publish(_CHANNEL_TEMPLATE.format(email=email), json.dumps({"type": "permissions_changed"}))
    except Exception:
        logger.warning("Failed to publish permissions-changed event for %s:\n%s", email, traceback.format_exc())


async def session_event_stream(
    email: str, client_ip: str = "unknown", lease_token: str | None = None, access_token: str | None = None
) -> AsyncIterator[str]:
    """
    Yields Server-Sent-Events-formatted lines on `email`'s own channel
    until the client disconnects. One Valkey Pub/Sub subscription per open
    tab: fine at this app's scale (a handful of users, not millions
    of concurrent connections); a larger deployment would front this with
    a proper pub/sub fan-out layer instead of one subscription per
    connection.

    Deliberately does NOT poll request.is_disconnected() to end the loop
    early: this app's LoggingMiddleware (see logging/logging_middleware.py)
    is a BaseHTTPMiddleware, and Starlette's BaseHTTPMiddleware is documented
    to make is_disconnected() unreliable for a downstream streaming endpoint
    - it was observed returning True on the very first check even with a
    live client, closing this stream within milliseconds of opening it. The
    browser's EventSource then auto-reconnected in a tight loop, and any
    publish_permissions_changed()/publish_session_revoked() fired during one
    of the resulting gaps was silently lost (Valkey pub/sub doesn't replay to
    a subscriber that wasn't connected at publish time) - exactly the "stays
    on a just-revoked page until a manual refresh" bug this stream exists to
    prevent. A real disconnect is still caught without this check: the next
    `yield` after the socket closes fails to send, which surfaces here as
    asyncio.CancelledError (handled below) or propagates out to the finally
    block either way.

    Bounded instead by _MAX_CONNECTION_SECONDS (a periodic clean cutoff the
    client's EventSource just reconnects from) and _shutdown_event (an
    immediate clean stop on SIGTERM/reload) - see both module-level comments
    above. Neither closes the stream the way the old is_disconnected() bug
    did: that was closing within milliseconds of opening, over and over,
    with the client racing to reconnect the whole time. These fire at most
    once per _MAX_CONNECTION_SECONDS, or once, ever, per process shutdown -
    ordinary long-lived connections are unaffected in between.

    `access_token` (optional, passed by the route) is re-verified on every
    heartbeat cycle (at most once per _HEARTBEAT_SECONDS): without this, a
    connection opened with a valid token stayed open and kept its lease/
    pubsub slot for up to _MAX_CONNECTION_SECONDS even after that token was
    revoked mid-connection (logout-all, password change, a targeted
    revoke). The channel only ever carries a generic "something changed, go
    check" signal, never session/permission data, so the leaked-slot/stale-
    connection gap was defense-in-depth, not a data exposure - this closes
    it anyway rather than relying solely on the hard cap. None (no token
    passed, e.g. in a test that constructs the generator directly) skips
    the check, matching the old behavior.
    """
    owns_lease = lease_token is None
    if owns_lease:
        lease_token = await acquire_session_event_lease(email, client_ip)
        if lease_token is None:
            await capture_security_alert(
                SESSION_EVENT_CONNECTION_LIMIT_EXCEEDED,
                metadata={
                    "account_limit": settings.SESSION_EVENT_MAX_CONNECTIONS_PER_ACCOUNT,
                    "ip_limit": settings.SESSION_EVENT_MAX_CONNECTIONS_PER_IP,
                },
            )
            return

    channel = _CHANNEL_TEMPLATE.format(email=email)
    pubsub = valkey_client.pubsub()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _MAX_CONNECTION_SECONDS
    try:
        await pubsub.subscribe(channel)

        while True:
            # Non-blocking drain first, before honoring shutdown/cutoff:
            # Valkey can push a message into the local buffer before a
            # shutdown is noticed, and ending the stream without draining it
            # would silently lose an event that already arrived.
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            if message is not None:
                yield f"data: {message['data']}\n\n"
                continue

            if _shutdown_event.is_set():
                return

            remaining = deadline - loop.time()
            if remaining <= 0:
                return

            get_message_task = asyncio.ensure_future(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=min(_HEARTBEAT_SECONDS, remaining))
            )
            shutdown_task = asyncio.ensure_future(_shutdown_event.wait())
            try:
                done, pending = await asyncio.wait(
                    {get_message_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
                )
            except asyncio.CancelledError:
                get_message_task.cancel()
                shutdown_task.cancel()
                raise
            for task in pending:
                task.cancel()

            if shutdown_task in done:
                return

            message = get_message_task.result()

            if message is None:
                if access_token is not None and await jwt_service.verify_token(access_token, "access") is None:
                    # The token that opened this connection is no longer
                    # valid (revoked, expired, version-bumped). End the
                    # stream instead of sending another heartbeat;
                    # EventSource reconnects on its own and the route's own
                    # GET /auth/session-events auth check rejects the
                    # reconnect if the client has nothing valid left either.
                    return
                # Nothing arrived within the heartbeat window: a comment
                # line (SSE ignores lines starting with ":"), not a real
                # event, purely to keep the connection alive.
                yield ": heartbeat\n\n"
                continue

            yield f"data: {message['data']}\n\n"

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("Session event stream for %s ended unexpectedly:\n%s", email, traceback.format_exc())
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        if owns_lease and lease_token is not None:
            await release_session_event_lease(email, client_ip, lease_token)
