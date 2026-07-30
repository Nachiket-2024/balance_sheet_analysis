# tests/backend/mystic_auth/unit/test_correlation_id_middleware_unit.py
#
# Unit coverage for CorrelationIdMiddleware : every response must carry an
# X-Request-ID header, either echoing an upstream-supplied one or generating
# a fresh UUID4, and the contextvar it sets must be visible to code running
# further down the middleware/route stack (which is how logging_config.py's
# RequestIdFilter tags every log line for the request).
import uuid

from backend.mystic_auth.logging.correlation_id_middleware import (
    REQUEST_ID_HEADER,
    CorrelationIdMiddleware,
    request_id_ctx_var,
)
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _build_app():
    seen_context_ids = []

    async def endpoint(request):
        # Confirm the contextvar is populated by the time the route runs
        seen_context_ids.append(request_id_ctx_var.get())
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationIdMiddleware)
    return app, seen_context_ids


def test_generates_a_request_id_when_none_supplied():
    app, seen_context_ids = _build_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    request_id = response.headers[REQUEST_ID_HEADER]
    # Must be a valid UUID4 string
    uuid.UUID(request_id)
    assert seen_context_ids == [request_id]


def test_echoes_an_upstream_supplied_request_id():
    app, seen_context_ids = _build_app()
    client = TestClient(app)

    response = client.get("/", headers={REQUEST_ID_HEADER: "upstream-id-123"})

    assert response.headers[REQUEST_ID_HEADER] == "upstream-id-123"
    assert seen_context_ids == ["upstream-id-123"]


def test_contextvar_resets_to_default_outside_a_request():
    assert request_id_ctx_var.get() == "-"


def test_rejects_malformed_upstream_request_id_and_generates_a_fresh_one():
    # An upstream-supplied ID is persisted verbatim into the audit log and
    # structured logs, so anything outside the safe charset/length must be
    # replaced with a generated UUID rather than trusted through.
    app, seen_context_ids = _build_app()
    client = TestClient(app)

    response = client.get("/", headers={REQUEST_ID_HEADER: "not valid! <script>"})

    request_id = response.headers[REQUEST_ID_HEADER]
    uuid.UUID(request_id)
    assert seen_context_ids == [request_id]


def test_rejects_oversized_upstream_request_id():
    app, seen_context_ids = _build_app()
    client = TestClient(app)

    response = client.get("/", headers={REQUEST_ID_HEADER: "a" * 500})

    request_id = response.headers[REQUEST_ID_HEADER]
    uuid.UUID(request_id)
    assert seen_context_ids == [request_id]
