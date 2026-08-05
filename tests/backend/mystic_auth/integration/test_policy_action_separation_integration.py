# tests/backend/mystic_auth/integration/test_policy_action_separation_integration.py
#
# Proves the old coarse "policies:manage" is genuinely gone: a caller
# holding only one of policies:read/create/update/delete/assign/revoke is
# authorized on the matching route(s) only, and denied (403) on every other
# policy-management route across policy_crud_routes.py and
# policy_assignment_routes.py. Split out of what used to be one 568-line
# test_authorization_routes_integration.py: kept as its own file (rather
# than folded into either routes file's test file) since each test here
# exercises both CRUD and assignment routes together in one pass.
import pytest
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database

from .authorization_test_accounts import (
    cleanup_test_policies,
    create_user_with_custom_policy_actions,
    create_verified_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]


async def _attempt_policy_routes(client, target_email):
    """As the currently logged-in caller, attempts every policy-management
    route against a disposable policy, returning {action: status_code}.
    A 403 means the authorization dependency denied the caller; any other
    status (200/201/404/409/...) means the caller was authorized to reach
    the route handler, regardless of the handler's functional outcome."""
    policy_name = unique_policy_name()

    create_resp = await client.post(
        "/authorization/policies",
        json={"name": policy_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    statuses = {"create": create_resp.status_code}

    # The remaining checks need a real policy row to target regardless of
    # whether "create" itself was authorized: create it directly via the
    # repository, bypassing the API, if the API call was denied.
    if create_resp.status_code != 201:
        async with database.async_session() as session:
            await policy_repository.create(
                {
                    "name": policy_name,
                    "actions": ["projects:read"],
                    "resource_type": "projects",
                    "conditions": None,
                },
                session,
            )

    statuses["read_list"] = (await client.get("/authorization/policies")).status_code
    statuses["read_get"] = (await client.get(f"/authorization/policies/{policy_name}")).status_code
    statuses["update"] = (
        await client.put(f"/authorization/policies/{policy_name}", json={"description": "updated"})
    ).status_code
    statuses["assign"] = (
        await client.post(f"/authorization/users/{target_email}/policies", json={"policy_name": policy_name})
    ).status_code
    statuses["revoke"] = (
        await client.delete(f"/authorization/users/{target_email}/policies/{policy_name}")
    ).status_code
    statuses["delete"] = (await client.delete(f"/authorization/policies/{policy_name}")).status_code
    return statuses


@pytest.mark.asyncio
async def test_policies_read_only_can_read_but_not_write(client, created_emails):
    email = unique_email("read-only")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_user_with_custom_policy_actions(client, created_emails, email, ["policies:read"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["read_list"] != 403
    assert statuses["read_get"] != 403
    for action in ("create", "update", "delete", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_create_only_cannot_read_update_delete_assign_or_revoke(client, created_emails):
    email = unique_email("create-only")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_user_with_custom_policy_actions(client, created_emails, email, ["policies:create"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["create"] != 403
    for action in ("read_list", "read_get", "update", "delete", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_update_only_cannot_read_create_delete_assign_or_revoke(client, created_emails):
    email = unique_email("update-only")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_user_with_custom_policy_actions(client, created_emails, email, ["policies:update"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["update"] != 403
    for action in ("read_list", "read_get", "create", "delete", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_delete_only_cannot_read_create_update_assign_or_revoke(client, created_emails):
    email = unique_email("delete-only")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_user_with_custom_policy_actions(client, created_emails, email, ["policies:delete"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["delete"] != 403
    for action in ("read_list", "read_get", "create", "update", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_assign_only_cannot_read_create_update_delete_or_revoke(client, created_emails):
    email = unique_email("assign-only")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_user_with_custom_policy_actions(client, created_emails, email, ["policies:assign"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["assign"] != 403
    for action in ("read_list", "read_get", "create", "update", "delete", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_revoke_only_cannot_read_create_update_delete_or_assign(client, created_emails):
    email = unique_email("revoke-only")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_user_with_custom_policy_actions(client, created_emails, email, ["policies:revoke"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["revoke"] != 403
    for action in ("read_list", "read_get", "create", "update", "delete", "assign"):
        assert statuses[action] == 403
