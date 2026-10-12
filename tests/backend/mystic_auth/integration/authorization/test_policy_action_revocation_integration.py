# tests/backend/mystic_auth/integration/authorization/test_policy_action_revocation_integration.py
#
# End-to-end coverage for POST /authorization/users/{email}/policies/{name}/
# revoke-action (backend/mystic_auth/api/pbac_routes/policies/policy_assignment_routes.py):
# carving one action out of a user's policy assignment while preserving the
# rest, against the real ASGI app, real PostgreSQL, and real Valkey. Proves
# the outcome end-to-end (the revoked action stops authorizing, every other
# action the policy granted keeps authorizing), not just that rows changed.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database

from .authorization_test_accounts import (
    PASSWORD,
    cleanup_test_policies,
    create_system_user,
    create_verified_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]


async def _create_multi_action_policy(actions: list[str], resource_type: str = "reports") -> str:
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": actions, "resource_type": resource_type, "conditions": None},
            session,
        )
    return policy_name


async def _authorized(client, email: str, action: str, resource_type: str = "reports") -> bool:
    resp = await client.post(
        f"/authorization/users/{email}/authorization-check",
        json={"action": action, "resource_type": resource_type},
    )
    assert resp.status_code == 200
    return resp.json()["authorized"]


@pytest.mark.asyncio
async def test_revoking_one_action_keeps_the_other_actions_authorized(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_multi_action_policy(["reports:view", "reports:export", "reports:delete"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    # authorization-check itself requires policies:read, which target_email
    # doesn't hold - stay logged in as system_email (which does) throughout;
    # it evaluates whichever user_email is in the URL, not the caller.
    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert await _authorized(client, target_email, "reports:view")
    assert await _authorized(client, target_email, "reports:export")
    assert await _authorized(client, target_email, "reports:delete")

    resp = await client.post(
        f"/authorization/users/{target_email}/policies/{policy_name}/revoke-action",
        json={"action": "reports:view"},
    )
    assert resp.status_code == 200

    # The cache must actually be bypassed/refreshed, not just the DB row
    # changed: authorize() is called fresh here, same as any real request.
    assert not await _authorized(client, target_email, "reports:view")
    assert await _authorized(client, target_email, "reports:export")
    assert await _authorized(client, target_email, "reports:delete")

    # The policy assignment itself is gone (converted to direct grants) -
    # confirms this isn't just deactivating one action inside the policy,
    # which would also affect every OTHER holder of the policy.
    policies_resp = await client.get(f"/authorization/users/{target_email}/policies")
    assert policy_name not in {p["name"] for p in policies_resp.json()["policies"]}

    permissions_resp = await client.get(f"/authorization/users/{target_email}/permissions")
    direct_actions = {p["action"] for p in permissions_resp.json()["permissions"]}
    assert "reports:export" in direct_actions
    assert "reports:delete" in direct_actions
    assert "reports:view" not in direct_actions


@pytest.mark.asyncio
async def test_revoking_one_action_does_not_affect_other_holders_of_the_same_policy(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    other_holder_email = unique_email("other")
    policy_name = await _create_multi_action_policy(["reports:view", "reports:export"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_verified_user(client, created_emails, other_holder_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        f"/authorization/users/{target_email}/policies/{policy_name}/revoke-action",
        json={"action": "reports:view"},
    )
    assert resp.status_code == 200

    assert await _authorized(client, other_holder_email, "reports:view")
    assert await _authorized(client, other_holder_email, "reports:export")


@pytest.mark.asyncio
async def test_revoking_an_action_not_in_the_policy_returns_400(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_multi_action_policy(["reports:view"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        f"/authorization/users/{target_email}/policies/{policy_name}/revoke-action",
        json={"action": "reports:nonexistent"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_revoking_from_a_policy_the_user_does_not_hold_returns_404(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_multi_action_policy(["reports:view"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        f"/authorization/users/{target_email}/policies/{policy_name}/revoke-action",
        json={"action": "reports:view"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoking_a_policy_action_preserves_an_unrelated_existing_direct_grant(client, created_emails):
    """A user who separately already held a direct grant for one of the
    RETAINED actions (on the same resource_type) before this operation
    must keep it afterward, not have it clobbered by the policy-to-direct
    conversion."""
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_multi_action_policy(["reports:view", "reports:export"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "reports:export", "resource_type": "reports"},
    )
    assert grant_resp.status_code == 200

    resp = await client.post(
        f"/authorization/users/{target_email}/policies/{policy_name}/revoke-action",
        json={"action": "reports:view"},
    )
    assert resp.status_code == 200

    assert await _authorized(client, target_email, "reports:export")
    assert not await _authorized(client, target_email, "reports:view")
