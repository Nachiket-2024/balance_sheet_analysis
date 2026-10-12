# tests/backend/mystic_auth/integration/authorization/test_bulk_permission_assignment_integration.py
#
# End-to-end coverage for backend/mystic_auth/api/pbac_routes/bulk/bulk_permission_routes.py:
# fanning one chosen direct permission grant out across many users in one
# request. See test_bulk_policy_assignment_integration.py's module docstring
# for the split rationale (one file per bulk domain, each kept ~300 lines).
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.user_permission_repository import (
    user_permission_repository,
)
from backend.mystic_auth.database.connection import database

from .authorization_test_accounts import (
    PASSWORD,
    create_system_user,
    create_verified_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_bulk_assign_permissions_grants_direct_access_to_every_selected_user(client, created_emails):
    system_email = unique_email("system")
    target_a = unique_email("bulk-perm-a")
    target_b = unique_email("bulk-perm-b")
    await create_verified_user(client, created_emails, target_a, [SELF_SERVICE_POLICY_NAME])
    await create_verified_user(client, created_emails, target_b, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [
            {"user_email": target_a, "action": "users:list_all", "resource_type": "users"},
            {"user_email": target_b, "action": "users:list_all", "resource_type": "users"},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 2
    statuses = {r["user_email"]: r["status"] for r in body["results"]}
    assert statuses[target_a] == "success"
    assert statuses[target_b] == "success"

    for target in (target_a, target_b):
        await client.post("/auth/login", json={"email": target, "password": PASSWORD})
        allowed = await client.get("/users/")
        assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_bulk_assign_permissions_reports_already_held_when_unchanged(client, created_emails):
    """Re-granting the exact same (action, resource_type, conditions) a
    user already holds must be a true no-op, reported "already_held" - not
    a plain "success" that hides the fact nothing actually changed. See
    UserPermissionRepository.bulk_assign_permissions's own docstring."""
    system_email = unique_email("system")
    target = unique_email("bulk-perm-already-held")
    await create_verified_user(client, created_emails, target, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    first = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{"user_email": target, "action": "users:list_all", "resource_type": "users"}]},
    )
    assert first.json()["results"][0]["status"] == "success"

    second = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{"user_email": target, "action": "users:list_all", "resource_type": "users"}]},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["success_count"] == 1
    assert body["results"][0]["status"] == "already_held"


@pytest.mark.asyncio
async def test_bulk_assign_permissions_reports_success_not_already_held_when_conditions_change(client, created_emails):
    """Re-granting the same (action, resource_type) but with DIFFERENT
    conditions is a real update (the grant's scope changed), so it must
    still report "success", not "already_held"."""
    system_email = unique_email("system")
    target = unique_email("bulk-perm-conditions-change")
    await create_verified_user(client, created_emails, target, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    first = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{"user_email": target, "action": "users:list_all", "resource_type": "users"}]},
    )
    assert first.json()["results"][0]["status"] == "success"

    second = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{
            "user_email": target, "action": "users:list_all", "resource_type": "users",
            "conditions": {"time": {"start": "00:00", "end": "23:59", "timezone": "UTC"}},
        }]},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["results"][0]["status"] == "success"

    async with database.async_session() as session:
        grants = await user_permission_repository.get_permissions_for_user(target, session)
    matching = [g for g in grants if g.action == "users:list_all" and g.resource_type == "users"]
    assert len(matching) == 1
    assert matching[0].conditions == {"time": {"start": "00:00", "end": "23:59", "timezone": "UTC"}}


@pytest.mark.asyncio
async def test_bulk_remove_permissions_revokes_direct_access(client, created_emails):
    system_email = unique_email("system")
    target = unique_email("bulk-perm-remove")
    await create_verified_user(client, created_emails, target, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{"user_email": target, "action": "users:list_all", "resource_type": "users"}]},
    )
    assert grant_resp.json()["success_count"] == 1

    remove_resp = await client.post(
        "/authorization/bulk/permissions/remove",
        json={"items": [{"user_email": target, "action": "users:list_all", "resource_type": "users"}]},
    )
    assert remove_resp.status_code == 200
    assert remove_resp.json()["success_count"] == 1

    await client.post("/auth/login", json={"email": target, "password": PASSWORD})
    denied = await client.get("/users/")
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_bulk_remove_permissions_reports_not_held_without_blocking_other_items(client, created_emails):
    system_email = unique_email("system")
    holder = unique_email("bulk-perm-holder")
    non_holder = unique_email("bulk-perm-non-holder")
    await create_verified_user(client, created_emails, holder, [SELF_SERVICE_POLICY_NAME])
    await create_verified_user(client, created_emails, non_holder, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{"user_email": holder, "action": "users:list_all", "resource_type": "users"}]},
    )
    assert grant_resp.json()["success_count"] == 1

    resp = await client.post(
        "/authorization/bulk/permissions/remove",
        json={"items": [
            {"user_email": holder, "action": "users:list_all", "resource_type": "users"},
            {"user_email": non_holder, "action": "users:list_all", "resource_type": "users"},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    statuses = {r["user_email"]: (r["status"], r["error"]) for r in body["results"]}
    assert statuses[holder][0] == "success"
    assert statuses[non_holder] == ("error", "not_held")
