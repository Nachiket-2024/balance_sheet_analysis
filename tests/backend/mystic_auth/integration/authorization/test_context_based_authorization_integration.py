# tests/backend/mystic_auth/integration/authorization/test_context_based_authorization_integration.py
#
# End-to-end (DB-free) proof that a real request's context : built by
# build_authorization_context, never client-supplied : actually drives
# IP-based and time-based policy decisions through the real evaluator.
# Per the centralized authorization context design: add tests for
# IP-based authorization, time-based authorization, and missing-context
# denial.
from unittest.mock import MagicMock

from backend.mystic_auth.authorization.context.request_context_builder import (
    build_authorization_context,
)
from backend.mystic_auth.authorization.evaluators.policy_evaluator import (
    policy_evaluation_engine,
)
from backend.mystic_auth.authorization.models.policy_model import Policy


def _request(client_host):
    request = MagicMock()
    request.client.host = client_host
    return request


def _office_network_policy():
    return Policy(
        name="office_only",
        actions=["reports:view"],
        resource_type="reports",
        conditions={"network": {"allowed_ips": ["10.0.0.0/8"]}},
        is_active=True,
    )


def _business_hours_policy():
    return Policy(
        name="business_hours_only",
        actions=["reports:view"],
        resource_type="reports",
        conditions={"time": {"start": "09:00", "end": "17:00", "timezone": "UTC"}},
        is_active=True,
    )


# ---------------------------- IP-based authorization ----------------------------

def test_ip_based_authorization_allows_from_the_corporate_network():
    context = build_authorization_context(_request(client_host="10.1.2.3"))
    allowed = policy_evaluation_engine.evaluate(
        [_office_network_policy()], "reports:view", "reports", "user@example.com", context=context
    )
    assert allowed is True


def test_ip_based_authorization_denies_from_outside_the_corporate_network():
    context = build_authorization_context(_request(client_host="203.0.113.50"))
    allowed = policy_evaluation_engine.evaluate(
        [_office_network_policy()], "reports:view", "reports", "user@example.com", context=context
    )
    assert allowed is False


def test_ip_based_authorization_denies_when_connection_has_no_client_info():
    """Missing context denial: if the request has no discoverable client
    IP at all, an IP-gated policy must deny, never default-allow."""
    request = MagicMock()
    request.client = None
    context = build_authorization_context(request)

    allowed = policy_evaluation_engine.evaluate(
        [_office_network_policy()], "reports:view", "reports", "user@example.com", context=context
    )
    assert allowed is False


# ---------------------------- Time-based authorization ----------------------------

def test_time_based_authorization_allows_during_business_hours():
    request = _request(client_host="10.0.0.1")
    context = build_authorization_context(request)
    context["current_time"] = "2026-07-13T12:00:00+00:00"  # noon UTC : within 09:00-17:00

    allowed = policy_evaluation_engine.evaluate(
        [_business_hours_policy()], "reports:view", "reports", "user@example.com", context=context
    )
    assert allowed is True


def test_time_based_authorization_denies_outside_business_hours():
    request = _request(client_host="10.0.0.1")
    context = build_authorization_context(request)
    context["current_time"] = "2026-07-13T23:00:00+00:00"  # 11pm UTC : outside 09:00-17:00

    allowed = policy_evaluation_engine.evaluate(
        [_business_hours_policy()], "reports:view", "reports", "user@example.com", context=context
    )
    assert allowed is False


# ---------------------------- Missing context denial ----------------------------
# Only IP-gated policies have a meaningful "missing context" deny case:
# there is no sensible default IP. Time conditions always have a fallback
# (the real server clock), so "no context at all" is not itself a deny
# condition for them : see test_time_condition's own fail-safe coverage
# (missing start/end, invalid timezone) for that handler's actual
# fail-safe cases.

def test_ip_gated_policy_denies_with_no_context_at_all():
    allowed = policy_evaluation_engine.evaluate(
        [_office_network_policy()], "reports:view", "reports", "user@example.com", context=None
    )
    assert allowed is False
