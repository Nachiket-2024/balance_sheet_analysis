# tests/backend/mystic_auth/integration/authorization/test_purge_cache_invalidation_integration.py
#
# Proves user_purge_service.py's post-purge
# invalidate_user_policies/invalidate_user_permissions calls actually clear
# the real Valkey cache, against the real ASGI app, real PostgreSQL, and real
# Valkey - not just that the mocked collaborator was called
# (test_user_purge_service_unit.py covers that at the unit level). Two angles:
# the raw cache keys are gone from Valkey, AND a fresh signup reusing the same
# email starts with a clean effective-permission set rather than transiently
# inheriting the purged user's stale cached grants.
import pytest

from backend.mystic_auth.authorization.caching.authorization_cache_service import (
    _user_permissions_key,
    _user_policies_key,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.valkey.client import valkey_client

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
async def test_purge_clears_the_actual_valkey_cache_keys(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_policy(["reports:view"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})

    # Populate both cache namespaces for target_email.
    assert await _authorized(client, target_email, "reports:view")
    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "reports:export", "resource_type": "reports"},
    )
    assert grant_resp.status_code == 200
    assert await _authorized(client, target_email, "reports:export")

    assert await valkey_client.get(_user_policies_key(target_email)) is not None
    assert await valkey_client.get(_user_permissions_key(target_email)) is not None

    purge_resp = await client.delete(f"/users/{target_email}/purge")
    assert purge_resp.status_code == 200

    assert await valkey_client.get(_user_policies_key(target_email)) is None
    assert await valkey_client.get(_user_permissions_key(target_email)) is None


@pytest.mark.asyncio
async def test_fresh_signup_reusing_a_purged_email_starts_with_no_effective_permissions(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    policy_name = await _create_policy(["reports:view"])

    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})

    # Populate the cache with an "authorized" answer for target_email.
    assert await _authorized(client, target_email, "reports:view")

    purge_resp = await client.delete(f"/users/{target_email}/purge")
    assert purge_resp.status_code == 200

    # Re-create an account with the exact same email; it holds no policies at
    # all, so if the purged user's cached "authorized" answer leaked forward,
    # this fresh account would incorrectly inherit reports:view access.
    # create_verified_user leaves the client logged in as the new
    # target_email, which itself lacks policies:read to call
    # authorization-check - log back in as system_email to make the check.
    await create_verified_user(client, created_emails, target_email, [])
    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})

    assert not await _authorized(client, target_email, "reports:view")
