import asyncio
import json
import traceback
from collections.abc import AsyncIterator

from fastapi import Request

from ..logging.logging_config import get_logger
from ..redis.client import redis_client

logger = get_logger(__name__)

_CHANNEL_TEMPLATE = "session_events:{email}"

# How often the stream sends a keep-alive comment when no real event has
# arrived, so intermediate proxies/load balancers (and the browser's own
# idle-connection timeout) don't treat a quiet-but-healthy connection as
# dead and close it.
_HEARTBEAT_SECONDS = 20


async def publish_session_revoked(email: str) -> None:
    """
    Real-time nudge: tells every open tab/device currently holding a live
    GET /auth/session-events connection for this account to re-check its
    own session right now (a normal GET /auth/me / GET /auth/sessions
    refetch), instead of waiting for its next background poll or window-
    focus refetch. Best-effort and never raises: a Redis hiccup here must
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
        await redis_client.publish(_CHANNEL_TEMPLATE.format(email=email), json.dumps({"type": "revoked"}))
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
        await redis_client.publish(_CHANNEL_TEMPLATE.format(email=email), json.dumps({"type": "created"}))
    except Exception:
        logger.warning("Failed to publish session-created event for %s:\n%s", email, traceback.format_exc())


async def session_event_stream(email: str, request: Request) -> AsyncIterator[str]:
    """
    Yields Server-Sent-Events-formatted lines on `email`'s own channel
    until the client disconnects. One Redis Pub/Sub subscription per open
    tab: fine at this app's scale (a handful of users, not millions
    of concurrent connections); a larger deployment would front this with
    a proper pub/sub fan-out layer instead of one subscription per
    connection.
    """
    channel = _CHANNEL_TEMPLATE.format(email=email)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(channel)

        while True:
            if await request.is_disconnected():
                break

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_HEARTBEAT_SECONDS)

            if message is None:
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
