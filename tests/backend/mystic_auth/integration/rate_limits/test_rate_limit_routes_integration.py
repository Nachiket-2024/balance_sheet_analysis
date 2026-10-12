# End-to-end tests for GET /rate-limits/ and DELETE /rate-limits/{key} (the
# admin Rate Limit Dashboard) against the real app and Valkey. Permission
# setup mirrors authorization_test_accounts.create_user_with_custom_policy_actions,
# but grants rate_limits:read/rate_limits:reset instead of a policies:*
# action, and checks the two are enforced independently, same pattern as
# test_policy_action_separation_integration.py.
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

PASSWORD = "StrongPass123!"


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


async def _create_user_with_rate_limits_read(client, created_emails):
    return await _create_user_with_actions(client, created_emails, "ratelimitreader", ["rate_limits:read"])


async def _create_user_with_rate_limits_reset(client, created_emails):
    return await _create_user_with_actions(client, created_emails, "ratelimitreset", ["rate_limits:reset"])


async def _create_user_with_read_and_reset(client, created_emails):
    return await _create_user_with_actions(
        client, created_emails, "ratelimitfull", ["rate_limits:read", "rate_limits:reset"]
    )


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/rate-limits/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_list_rate_limits(client, created_emails):
    email = unique_email("plain")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/rate-limits/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_reset_rate_limits(client, created_emails):
    email = unique_email("plain")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.delete("/rate-limits/some_endpoint:ip:1.2.3.4")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_authorized_user_can_list_a_tripped_limiter_and_see_its_count(client, created_emails):
    await _create_user_with_rate_limits_read(client, created_emails)

    endpoint = f"test_dashboard_endpoint_{uuid.uuid4().hex}"
    key = f"{endpoint}:ip:203.0.113.5"
    try:
        # Calls the same primitive the rate_limited decorator uses, instead
        # of hitting a real rate-limited route N times to trip it.
        await rate_limiter_service.record_request(key)
        await rate_limiter_service.record_request(key)

        resp = await client.get("/rate-limits/", params={"endpoint": endpoint})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entries"]) == 1
        entry = body["entries"][0]
        assert entry["key"] == key
        assert entry["endpoint"] == endpoint
        assert entry["scope"] == "ip"
        assert entry["identifier"] == "203.0.113.5"
        assert entry["count"] == 2
        assert entry["limit"] == rate_limiter_service.MAX_REQUESTS_PER_WINDOW
        assert entry["resets_in_seconds"] is not None and entry["resets_in_seconds"] > 0
    finally:
        await valkey_client.delete(key)


@pytest.mark.asyncio
async def test_read_authorized_user_can_get_rate_limit_summary(client, created_emails):
    await _create_user_with_rate_limits_read(client, created_emails)

    endpoint = f"test_dashboard_summary_{uuid.uuid4().hex}"
    key = f"{endpoint}:ip:203.0.113.30"
    try:
        await rate_limiter_service.record_request(key)
        resp = await client.get("/rate-limits/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert body["by_endpoint"][endpoint] == 1
        assert body["by_scope"]["ip"] >= 1
    finally:
        await valkey_client.delete(key)


@pytest.mark.asyncio
async def test_scope_filter_excludes_the_other_scope(client, created_emails):
    await _create_user_with_rate_limits_read(client, created_emails)

    endpoint = f"test_dashboard_scope_{uuid.uuid4().hex}"
    ip_key = f"{endpoint}:ip:203.0.113.9"
    account_key = f"{endpoint}:account:victim@example.com"
    try:
        await rate_limiter_service.record_request(ip_key)
        await rate_limiter_service.record_request(account_key)

        ip_only = (await client.get("/rate-limits/", params={"endpoint": endpoint, "scope": "ip"})).json()
        assert [e["key"] for e in ip_only["entries"]] == [ip_key]

        account_only = (await client.get("/rate-limits/", params={"endpoint": endpoint, "scope": "account"})).json()
        assert [e["key"] for e in account_only["entries"]] == [account_key]
    finally:
        await valkey_client.delete(ip_key)
        await valkey_client.delete(account_key)


@pytest.mark.asyncio
async def test_scope_filter_accepts_email_scope(client, created_emails):
    # Regression test: the route's scope Query pattern used to be
    # ^(ip|account)$, so "email" (a real RateLimitEntry.scope value, and an
    # option the frontend's scope filter offers) 422'd instead of filtering.
    await _create_user_with_rate_limits_read(client, created_emails)

    endpoint = f"test_dashboard_email_scope_{uuid.uuid4().hex}"
    email_key = f"{endpoint}:email:victim@example.com"
    try:
        await rate_limiter_service.record_request(email_key)

        resp = await client.get("/rate-limits/", params={"endpoint": endpoint, "scope": "email"})
        assert resp.status_code == 200
        assert [e["key"] for e in resp.json()["entries"]] == [email_key]
    finally:
        await valkey_client.delete(email_key)


@pytest.mark.asyncio
async def test_rate_limits_read_only_cannot_reset(client, created_emails):
    await _create_user_with_rate_limits_read(client, created_emails)

    endpoint = f"test_dashboard_read_only_{uuid.uuid4().hex}"
    key = f"{endpoint}:ip:203.0.113.21"
    await rate_limiter_service.record_request(key)
    try:
        resp = await client.delete(f"/rate-limits/{key}")
        assert resp.status_code == 403
        assert await valkey_client.get(key) is not None
    finally:
        await valkey_client.delete(key)


@pytest.mark.asyncio
async def test_rate_limits_reset_only_cannot_list(client, created_emails):
    await _create_user_with_rate_limits_reset(client, created_emails)

    resp = await client.get("/rate-limits/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_authorized_user_can_reset_a_tripped_limiter(client, created_emails):
    await _create_user_with_rate_limits_reset(client, created_emails)

    endpoint = f"test_dashboard_reset_{uuid.uuid4().hex}"
    key = f"{endpoint}:ip:203.0.113.20"
    await rate_limiter_service.record_request(key)
    assert await valkey_client.get(key) is not None

    resp = await client.delete(f"/rate-limits/{key}")
    assert resp.status_code == 204
    assert await valkey_client.get(key) is None


@pytest.mark.asyncio
async def test_resetting_an_already_absent_key_is_idempotent(client, created_emails):
    await _create_user_with_rate_limits_reset(client, created_emails)

    resp = await client.delete("/rate-limits/never_existed:ip:0.0.0.0")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_user_with_both_actions_can_list_and_reset(client, created_emails):
    await _create_user_with_read_and_reset(client, created_emails)

    endpoint = f"test_dashboard_both_{uuid.uuid4().hex}"
    key = f"{endpoint}:ip:203.0.113.22"
    await rate_limiter_service.record_request(key)
    try:
        list_resp = await client.get("/rate-limits/", params={"endpoint": endpoint})
        assert list_resp.status_code == 200
        assert len(list_resp.json()["entries"]) == 1

        delete_resp = await client.delete(f"/rate-limits/{key}")
        assert delete_resp.status_code == 204
    finally:
        await valkey_client.delete(key)
