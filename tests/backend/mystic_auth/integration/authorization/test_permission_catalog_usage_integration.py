# tests/backend/mystic_auth/integration/authorization/test_permission_catalog_usage_integration.py
#
# End-to-end coverage for GET /authorization/permissions/catalog/usage
# (permission_catalog_routes.py, PermissionUsageRepository): who actually
# holds each catalog action right now, folding active Policy/UserPolicy
# assignments and active direct UserPermission grants together. Backs the
# Permissions page's "Held by" column, its quick filters, and the details
# dialog - see .project/permissions-page-review.md.
import pytest

from backend.mystic_auth.authorization.permissions_catalog import PERMISSION_CATALOG
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)

from .authorization_test_accounts import (
    PASSWORD,
    create_system_user,
    create_user_with_custom_policy_actions,
    create_verified_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_usage_returned_for_every_catalog_action(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog/usage")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(PERMISSION_CATALOG)
    actions = {entry["action"] for entry in body}
    assert actions == {entry.action for entry in PERMISSION_CATALOG}
    for entry in body:
        assert isinstance(entry["policies"], list)
        assert isinstance(entry["direct_grant_count"], int)
        assert isinstance(entry["policy_user_count"], int)
        assert isinstance(entry["total_user_count"], int)


@pytest.mark.asyncio
async def test_usage_denied_without_permissions_read(client, created_emails):
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog/usage")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_usage_denied_for_caller_with_only_policies_create(client, created_emails):
    """Unlike the catalog itself, usage discloses who holds what, so it's
    gated by permissions:read alone, not CATALOG_READ_DEPENDENCY's broader
    allow-list."""
    target_email = unique_email("creator")
    await create_user_with_custom_policy_actions(client, created_emails, target_email, ["policies:create"])

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog/usage")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_usage_counts_reflect_one_policy_and_one_direct_grant(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    policy_holder_email = unique_email("policyholder")
    # self_service grants users:read_own/users:update_own; a fresh caller
    # with just that policy exercises the "held via policy" path without
    # touching the seeded baseline policies' own user counts.
    await create_verified_user(client, created_emails, policy_holder_email, [SELF_SERVICE_POLICY_NAME])

    direct_grant_email = unique_email("directgrant")
    await create_verified_user(client, created_emails, direct_grant_email, [])

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        f"/authorization/users/{direct_grant_email}/permissions",
        json={"action": "security_audit:read", "resource_type": "security_audit"},
    )
    assert grant_resp.status_code == 200

    resp = await client.get("/authorization/permissions/catalog/usage")
    assert resp.status_code == 200
    by_action = {entry["action"]: entry for entry in resp.json()}

    read_own = by_action["users:read_own"]
    assert SELF_SERVICE_POLICY_NAME in {p["name"] for p in read_own["policies"]}
    assert read_own["total_user_count"] >= 1

    audit_read = by_action["security_audit:read"]
    assert audit_read["direct_grant_count"] >= 1
    assert audit_read["total_user_count"] >= 1


@pytest.mark.asyncio
async def test_usage_direct_grant_raises_only_the_granted_actions_count(client, created_emails):
    """A dev DB seeded with baseline policies (e.g. the design-preview
    account) means no catalog action is guaranteed to start at zero
    holders, so this asserts the delta a fresh direct grant causes rather
    than an absolute zero. Granting rate_limits:reset to a brand new user
    must raise exactly that action's direct_grant_count/total_user_count by
    one and must not touch an unrelated action (users:read_own)."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    login_email = unique_email("reader")
    await create_verified_user(client, created_emails, login_email, [SELF_SERVICE_POLICY_NAME])

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    before_resp = await client.get("/authorization/permissions/catalog/usage")
    assert before_resp.status_code == 200
    before_by_action = {entry["action"]: entry for entry in before_resp.json()}

    grant_resp = await client.post(
        f"/authorization/users/{login_email}/permissions",
        json={"action": "rate_limits:reset", "resource_type": "rate_limits"},
    )
    assert grant_resp.status_code == 200

    after_resp = await client.get("/authorization/permissions/catalog/usage")
    assert after_resp.status_code == 200
    after_by_action = {entry["action"]: entry for entry in after_resp.json()}

    reset_before, reset_after = before_by_action["rate_limits:reset"], after_by_action["rate_limits:reset"]
    assert reset_after["direct_grant_count"] == reset_before["direct_grant_count"] + 1
    assert reset_after["total_user_count"] == reset_before["total_user_count"] + 1

    read_own_before, read_own_after = before_by_action["users:read_own"], after_by_action["users:read_own"]
    assert read_own_after == read_own_before
