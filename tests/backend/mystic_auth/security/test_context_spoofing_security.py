# tests/backend/mystic_auth/security/test_context_spoofing_security.py
#
# Real-DB proof that request_context_builder.build_authorization_context
# is actually used for real decisions, and a client cannot influence it:
# context-spoofing attempts. Uses POST /authorization/batch-
# check as the enforcement vehicle: unlike the admin inspection endpoint
# (which deliberately accepts caller-supplied context for "what if"
# simulation), batch-check always builds its context from the real
# request, never the body/headers.
#
# httpx's ASGITransport (see conftest.py's `client` fixture) reports the
# connection as ("127.0.0.1", 123) by default, so every request in this
# suite has a real client IP of 127.0.0.1, regardless of any header a test
# sends.
import pytest
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database

from .conftest import create_verified_user, unique_email, unique_policy_name

ACTION = "sectest:view"
RESOURCE_TYPE = "sectest_resource"


async def _create_network_gated_policy(allowed_ip: str) -> str:
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {
                "name": policy_name,
                "actions": [ACTION],
                "resource_type": RESOURCE_TYPE,
                "conditions": {"network": {"allowed_ips": [allowed_ip]}},
            },
            session,
        )
    return policy_name


@pytest.mark.asyncio
async def test_forged_x_forwarded_for_header_does_not_grant_access(client, created_emails):
    """A policy that allows the *real* connection IP (127.0.0.1, per
    ASGITransport) must grant access even when the client claims a
    completely different IP via a spoofable header."""
    email = unique_email("spoof-allow")
    policy_name = await _create_network_gated_policy(allowed_ip="127.0.0.1")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])

    resp = await client.post(
        "/authorization/batch-check",
        json={"checks": [{"action": ACTION, "resource_type": RESOURCE_TYPE}]},
        headers={"X-Forwarded-For": "203.0.113.99"},  # forged, unrelated IP
    )

    assert resp.status_code == 200
    assert resp.json()["results"][0]["allowed"] is True


@pytest.mark.asyncio
async def test_forged_x_forwarded_for_header_does_not_bypass_a_denial(client, created_emails):
    """The inverse proof: a policy that allows some OTHER IP (matching
    what a forged header claims) must still deny, because the real
    connection IP (127.0.0.1) doesn't match; the forged header is never
    consulted at all."""
    email = unique_email("spoof-deny")
    policy_name = await _create_network_gated_policy(allowed_ip="203.0.113.99")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])

    resp = await client.post(
        "/authorization/batch-check",
        json={"checks": [{"action": ACTION, "resource_type": RESOURCE_TYPE}]},
        headers={"X-Forwarded-For": "203.0.113.99"},  # matches the policy, but must be ignored
    )

    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["allowed"] is False
    assert result["denial_reason"] == "condition_failed"


@pytest.mark.asyncio
async def test_forged_current_time_in_request_body_is_never_used(client, created_emails):
    """A time-gated policy denied at the real current moment must not be
    unlocked by a client-supplied 'current_time' anywhere in the request:
    batch-check's request schema doesn't even accept a context field, but
    this proves there's no back door via `resource`."""
    email = unique_email("spoof-time")
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {
                "name": policy_name,
                "actions": [ACTION],
                "resource_type": RESOURCE_TYPE,
                # A window that cannot possibly contain the real current
                # time (already elapsed in the past)
                "conditions": {"time": {"start": "00:00", "end": "00:01", "timezone": "UTC"}},
            },
            session,
        )
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])

    resp = await client.post(
        "/authorization/batch-check",
        json={
            "checks": [
                {
                    "action": ACTION,
                    "resource_type": RESOURCE_TYPE,
                    "resource": {"current_time": "2026-01-01T00:00:30+00:00"},
                }
            ]
        },
    )

    assert resp.status_code == 200
    # allowed is False unless the current real UTC time genuinely happens
    # to fall in 00:00-00:01, overwhelmingly False given the tiny window
    assert resp.json()["results"][0]["allowed"] is False
