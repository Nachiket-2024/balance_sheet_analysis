# Proves that policy update/deactivate and direct-permission revoke actually
# invalidate the authorization cache end-to-end (real app, Postgres, Valkey).
# The unit test only checks the invalidation method was *called*; this checks
# the authorization *decision* itself flips on a repeated, cache-populating check.
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


async def _create_policy(actions: list[str], resource_type: str = "reports") -> str:
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
async def test_narrowing_policy_actions_flips_authorization_after_cache_was_populated(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_policy(["reports:view", "reports:export"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})

    # Populate the cache with a fresh DB-read result.
    assert await _authorized(client, target_email, "reports:export")

    update_resp = await client.put(
        f"/authorization/policies/{policy_name}",
        json={"actions": ["reports:view"]},
    )
    assert update_resp.status_code == 200

    # Same check, same cache key: must reflect the narrowed policy, not the
    # stale cached "authorized" answer from before the update.
    assert not await _authorized(client, target_email, "reports:export")
    assert await _authorized(client, target_email, "reports:view")


@pytest.mark.asyncio
async def test_deactivating_policy_flips_authorization_after_cache_was_populated(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_policy(["reports:view"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})

    assert await _authorized(client, target_email, "reports:view")

    update_resp = await client.put(
        f"/authorization/policies/{policy_name}",
        json={"is_active": False},
    )
    assert update_resp.status_code == 200

    assert not await _authorized(client, target_email, "reports:view")


@pytest.mark.asyncio
async def test_revoking_direct_permission_flips_authorization_after_cache_was_populated(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})

    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "reports:view", "resource_type": "reports"},
    )
    assert grant_resp.status_code == 200

    # Populate the cache with the "authorized" answer.
    assert await _authorized(client, target_email, "reports:view")

    revoke_resp = await client.delete(
        f"/authorization/users/{target_email}/permissions/reports:view",
        params={"resource_type": "reports"},
    )
    assert revoke_resp.status_code == 200

    # Same check, same cache key: must reflect the revoke, not the stale
    # cached "authorized" answer from before it.
    assert not await _authorized(client, target_email, "reports:view")
