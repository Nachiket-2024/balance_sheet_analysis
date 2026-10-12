import asyncio
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import httpx
import sentry_sdk
from fastapi import Request

from ..auth.token_logic.jwt_service import jwt_service
from ..core.settings import settings
from ..logging.logging_config import get_startup_logger

# Whether error monitoring is enabled is boot-relevant, so it goes to
# docker compose logs directly, unlike get_logger()'s routine file-only
# INFO logging elsewhere in this app.
startup_logger = get_startup_logger(__name__)

# Same path docker/mystic_auth/compose/docker-compose.dev.yml's backend service reads at boot, written once
# by bugsink-seed. Hardcoded rather than a Settings field since it's an
# internal compose-wiring detail, not something a downstream project would
# change on its own.
_BUGSINK_BACKEND_DSN_FILE = Path("/shared/bugsink-dsn/backend.env")
_DSN_LINE_RE = re.compile(r"^export SENTRY_DSN=(.+)$")


def init_sentry() -> None:
    """Initializes the Sentry SDK if SENTRY_DSN is configured, a no-op
    otherwise. Call once at import time, before the app starts serving
    requests (see main.py).

    Works against Sentry itself or any self-hosted server speaking the
    same protocol (e.g. Bugsink: see docs/mystic_auth/error-monitoring/overview.md).

    Never lets a bad SENTRY_DSN take the app down: sentry_sdk.init() can
    raise on a malformed DSN, and this runs at import time before main.py's
    global_exception_handler exists to catch it, so a typo in an optional
    setting would otherwise crash startup. Caught broadly, not just the
    known BadDsn case, since any init-time failure here should degrade the
    same way: monitoring off, app starts regardless.
    """
    if not settings.SENTRY_DSN:
        startup_logger.info("SENTRY_DSN not set : error monitoring disabled.")
        return

    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
            # No use for tracing/performance sampling here, so 0% keeps every
            # event an intentional capture_exception() call (below) instead of
            # adding tracing overhead. Error capture itself is unaffected.
            traces_sample_rate=0.0,
            # send_default_pii stays at its sentry-sdk default (False). User
            # identification is attached explicitly and narrowly (just an
            # email, via set_user in capture_exception below) instead of via
            # the SDK's broader automatic PII collection, which could
            # otherwise capture credentials in transit.
        )
    except Exception:
        startup_logger.warning(
            "SENTRY_DSN is set but the Sentry SDK failed to initialize : "
            "error monitoring is disabled for this run. Check the DSN value.",
            exc_info=True,
        )
        return

    startup_logger.info(
        "Sentry-protocol error monitoring initialized (environment=%s).",
        settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
    )


async def watch_for_late_dsn(poll_interval: float = 2.0, timeout_seconds: float = 300.0) -> None:
    """Background fallback for when init_sentry() ran with SENTRY_DSN still
    unset. Started from main.py's lifespan as fire-and-forget, never
    awaited on the request path, so it can't delay or block the app.

    docker/mystic_auth/compose/docker-compose.dev.yml's backend already waits ~10s at the shell level for
    bugsink-seed to write the DSN file before uvicorn starts. That's fine
    for a warm restart, but not a cold boot, where Bugsink's own first-run
    migrations can take 20+ seconds, past that window. Without this,
    SENTRY_DSN would stay unset for the process's life; this picks it up
    whenever it actually appears.

    No-ops if SENTRY_DSN is already set, or if BUGSINK_SUPERUSER_EMAIL isn't
    set (checked via the raw env var since Bugsink's presence is a
    deploy-time compose concern, not part of this app's config schema).

    Bounded at `timeout_seconds` (default 5min) so a genuinely broken
    Bugsink doesn't poll forever; gives up with one log line past that.
    """
    if settings.SENTRY_DSN:
        return
    if not os.environ.get("BUGSINK_SUPERUSER_EMAIL"):
        return

    elapsed = 0.0
    while elapsed < timeout_seconds:
        # Off the event loop: Path.exists()/.read_text() are blocking
        # syscalls, and this loop shares a process with every real request,
        # so a stall here would delay request handling for everyone.
        exists = await asyncio.to_thread(_BUGSINK_BACKEND_DSN_FILE.exists)
        if exists:
            content = await asyncio.to_thread(_BUGSINK_BACKEND_DSN_FILE.read_text)
            match = _DSN_LINE_RE.match(content.strip())
            if match:
                settings.SENTRY_DSN = match.group(1)
                init_sentry()
            return
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    startup_logger.info(
        "Gave up waiting for Bugsink's DSN file after %.0fs. Error monitoring stays "
        "off for this run. Restart the backend once Bugsink has finished starting to "
        "pick it up, or check `docker compose logs bugsink bugsink-seed` if this "
        "persists.",
        timeout_seconds,
    )


async def capture_exception(exc: Exception, request: Request | None = None) -> None:
    """Reports exc to the configured error-monitoring server. Safe to call
    even when init_sentry() was never invoked (SENTRY_DSN unset): the SDK's
    own capture_exception no-ops when no client is bound.

    Called from main.py's global_exception_handler, the one place every
    otherwise-unhandled exception passes through. That handler converts
    every exception to a generic 500 before it propagates as "unhandled"
    from Starlette's perspective, which is also where sentry-sdk's
    automatic instrumentation normally hooks in; without this explicit
    call, nothing would ever reach it unhandled.

    Best-effort attaches the caller's email as Sentry user context, read
    directly from the access_token cookie since this runs outside any
    route's own dependency chain (no current_user to reuse). A cookie
    that's missing, expired, or fails to verify just means no user context
    is attached; it never blocks the capture.
    """
    email = await _resolve_caller_email(request) if request is not None else None

    if email:
        sentry_sdk.set_user({"email": email})

    if request is not None:
        sentry_sdk.set_context("request", {"method": request.method, "path": request.url.path})

    sentry_sdk.capture_exception(exc)


async def capture_security_alert(
    event_type: str, metadata: Mapping[str, str | bool | int] | None = None
) -> None:
    """Send a security event to configured real-time alert sinks.

    The durable audit log remains the source of truth. This complementary
    Sentry/Bugsink event and optional internal webhook are metadata-only so
    alerting cannot become a second secret or token store. The webhook makes
    the delivery contract explicit for PagerDuty, Slack, Opsgenie, or an
    organization's internal incident gateway. Its short timeout and
    fail-open handling ensure monitoring outages never turn authentication
    into a 5xx.
    """
    payload = {
        "event_type": event_type,
        "environment": settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        "occurred_at": datetime.now(UTC).isoformat(),
        "metadata": metadata or {},
    }

    if settings.SECURITY_ALERT_WEBHOOK_URL:
        headers = {"content-type": "application/json"}
        if settings.SECURITY_ALERT_WEBHOOK_TOKEN:
            headers["authorization"] = f"Bearer {settings.SECURITY_ALERT_WEBHOOK_TOKEN}"
        try:
            async with httpx.AsyncClient(timeout=settings.SECURITY_ALERT_WEBHOOK_TIMEOUT_SECONDS) as client:
                response = await client.post(settings.SECURITY_ALERT_WEBHOOK_URL, json=payload, headers=headers)
                response.raise_for_status()
        except Exception:
            startup_logger.critical(
                "Security alert webhook failed for %s; inspect the durable audit event and webhook health",
                event_type,
                exc_info=True,
            )

    try:
        with sentry_sdk.new_scope() as scope:
            scope.set_level("error")
            scope.set_tag("security_event", event_type)
            if metadata:
                scope.set_extra("security_event_metadata", metadata)
            sentry_sdk.capture_message(f"Security alert: {event_type}", level="error")
    except Exception:
        startup_logger.warning("Unable to publish security alert %s", event_type, exc_info=True)


async def _resolve_caller_email(request: Request) -> str | None:
    access_token = request.cookies.get("access_token")
    if not access_token:
        return None

    payload = await jwt_service.verify_token(access_token, expected_type="access")
    return payload.get("email") if payload else None
