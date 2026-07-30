import re
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Holds the current request's correlation ID for the lifetime of that
# request's async task. Read by logging_config.py's request-id filter so
# every log line emitted while handling a request is automatically tagged
# with it, without threading the ID through every function signature.
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")

# Name of the header used both to accept an upstream-supplied ID (e.g. from a
# reverse proxy or load balancer) and to echo it back on the response.
REQUEST_ID_HEADER = "X-Request-ID"

# Upstream-supplied IDs are persisted into the audit log and structured logs
# verbatim, so they're constrained to a safe, bounded charset before being
# trusted; anything else (oversized, control characters, etc.) is replaced
# with a freshly generated ID instead of being propagated.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns/reuses a correlation ID and attaches it to request, context, and response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request, call_next):
        upstream_request_id = request.headers.get(REQUEST_ID_HEADER)
        if upstream_request_id and _VALID_REQUEST_ID.match(upstream_request_id):
            request_id = upstream_request_id
        else:
            request_id = str(uuid4())

        # Make the ID available on request.state and via the contextvar so
        # every log line emitted while handling this request (regardless of
        # which module logs it) can be tagged with it.
        request.state.request_id = request_id
        token = request_id_ctx_var.set(request_id)

        try:
            response = await call_next(request)
        finally:
            # Reset the contextvar so it doesn't leak into unrelated tasks.
            request_id_ctx_var.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
