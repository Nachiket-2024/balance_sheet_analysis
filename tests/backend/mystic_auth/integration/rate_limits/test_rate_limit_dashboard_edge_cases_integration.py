# Edge-case tests for GET /rate-limits/ and DELETE /rate-limits/{key}, split
# out from test_rate_limit_routes_integration.py: no-match filters,
# concurrent resets of the same key, and identifiers with characters that
# need URL-encoding (e.g. "@" in an email-scoped identifier).
import asyncio
import uuid

import pytest

from backend.mystic_auth.auth.security.rate_limiting.rate_limiter_service import (
    rate_limiter_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.valkey.client import valkey_client

from ..authorization.authorization_test_accounts import (
    cleanup_test_policies,
    create_verified_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]


async def _create_user_with_actions(client, created_emails, email_prefix, actions):
    email = unique_email(email_prefix)
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": actions, "resource_type": "rate_limits", "conditions": None},
            session,
        )
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])
    return email


async def _create_user_with_read_and_reset(client, created_emails):
    return await _create_user_with_actions(
        client, created_emails, "ratelimitedge", ["rate_limits:read", "rate_limits:reset"]
    )


@pytest.mark.asyncio
async def test_endpoint_filter_matching_nothing_returns_an_empty_page(client, created_emails):
    await _create_user_with_read_and_reset(client, created_emails)

    resp = await client.get("/rate-limits/", params={"endpoint": f"nonexistent_{uuid.uuid4().hex}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_reset_accepts_an_at_sign_in_an_email_scoped_identifier(client, created_emails):
    await _create_user_with_read_and_reset(client, created_emails)

    endpoint = f"test_dashboard_email_reset_{uuid.uuid4().hex}"
    key = f"{endpoint}:email:victim+tag@example.com"
    await rate_limiter_service.record_request(key)
    assert await valkey_client.get(key) is not None

    resp = await client.delete(f"/rate-limits/{key}")
    assert resp.status_code == 204
    assert await valkey_client.get(key) is None


@pytest.mark.asyncio
async def test_concurrent_resets_of_the_same_key_both_succeed_idempotently(client, created_emails):
    await _create_user_with_read_and_reset(client, created_emails)

    endpoint = f"test_dashboard_concurrent_reset_{uuid.uuid4().hex}"
    key = f"{endpoint}:ip:203.0.113.30"
    await rate_limiter_service.record_request(key)
    try:
        results = await asyncio.gather(
            client.delete(f"/rate-limits/{key}"),
            client.delete(f"/rate-limits/{key}"),
        )
        assert [r.status_code for r in results] == [204, 204]
        assert await valkey_client.get(key) is None
    finally:
        await valkey_client.delete(key)
