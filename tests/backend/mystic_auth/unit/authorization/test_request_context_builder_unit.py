# tests/backend/mystic_auth/unit/test_request_context_builder_unit.py
#
# Unit coverage for build_authorization_context : the one place every real
# authorization check derives ip_address/current_time/security_context
# from (claude.md's "Wire Authorization Context Properly": centralized
# builder, never trust client-supplied values, IP from the connection,
# time from the server clock).
from datetime import UTC, datetime
from unittest.mock import MagicMock

from backend.mystic_auth.authorization.context.request_context_builder import build_authorization_context


def _request(client_host="203.0.113.7", headers=None, query_params=None):
    request = MagicMock()
    request.client.host = client_host
    request.headers = headers or {}
    request.query_params = query_params or {}
    return request


def test_ip_address_comes_from_the_actual_connection():
    request = _request(client_host="192.0.2.55")
    context = build_authorization_context(request)
    assert context["ip_address"] == "192.0.2.55"


def test_missing_client_connection_yields_none_ip_address():
    request = MagicMock()
    request.client = None
    context = build_authorization_context(request)
    assert context["ip_address"] is None


def test_current_time_is_a_recent_utc_iso_timestamp():
    before = datetime.now(UTC)
    context = build_authorization_context(_request())
    after = datetime.now(UTC)

    current_time = datetime.fromisoformat(context["current_time"])
    assert before <= current_time <= after


def test_security_context_defaults_to_empty_dict():
    context = build_authorization_context(_request())
    assert context["security_context"] == {}


def test_forged_x_forwarded_for_header_is_never_used():
    """The literal attacker scenario this builder exists to prevent: a
    client claiming a different IP via a spoofable header must not affect
    the ip_address this app actually authorizes against."""
    request = _request(client_host="203.0.113.7", headers={"X-Forwarded-For": "1.2.3.4"})
    context = build_authorization_context(request)
    assert context["ip_address"] == "203.0.113.7"


def test_client_supplied_current_time_query_param_is_never_used():
    """A client cannot influence current_time by passing it as a query
    param, header, or any other client-controlled input : only the
    server's own clock is ever read."""
    request = _request(query_params={"current_time": "2000-01-01T00:00:00+00:00"})
    context = build_authorization_context(request)
    parsed_year = datetime.fromisoformat(context["current_time"]).year
    assert parsed_year != 2000
