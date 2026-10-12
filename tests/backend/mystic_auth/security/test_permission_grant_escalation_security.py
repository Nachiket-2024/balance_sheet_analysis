# Checks that a caller holding only permissions:grant (not
# system_superuser) can't grant a sensitive action they don't already hold,
# to themselves or anyone else, via the single-item or bulk routes. Mirrors
# test_privilege_escalation_security.py's policies:assign coverage.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.authorization.repositories.user_permission_repository import (
    user_permission_repository,
)
from backend.mystic_auth.database.connection import database

from .conftest import (
    PASSWORD,
    create_system_user,
    create_user_with_custom_policy,
    create_verified_user,
    unique_email,
    unique_policy_name,
)


@pytest.mark.asyncio
async def test_permissions_grant_only_cannot_grant_an_unheld_sensitive_action(client, created_emails):
    email = unique_email("grant-escalate")
    await create_user_with_custom_policy(client, created_emails, email, ["permissions:grant"], resource_type="permissions")

    resp = await client.post(
        f"/authorization/users/{email}/permissions",
        json={"action": "users:delete_any", "resource_type": "users"},  # caller doesn't hold this
    )
    assert resp.status_code == 403
    # Specifically the "you don't hold this action at all" guard, not just
    # any 403 - a mutation that disables this exact check was once masked
    # by a second, coincidentally-also-403 check further down the same
    # function (CANNOT_GRANT_BROADER_CONDITIONS), so this test must pin the
    # code, not just the status.
    assert resp.json()["code"] == "CANNOT_GRANT_UNHELD_ACTION"

    # confirm it didn't take
    list_resp = await client.get("/authorization/users/me/permissions")
    assert list_resp.status_code == 200
    assert list_resp.json()["permissions"] == []


@pytest.mark.asyncio
async def test_permissions_grant_only_cannot_self_escalate_to_users_purge_via_bulk_endpoint(
    client, created_emails
):
    """Passing the route-level permissions:grant check shouldn't skip the
    per-item guard: tries self-escalation through the bulk path instead of
    the single-item one."""
    email = unique_email("bulk-grant-escalate")
    await create_user_with_custom_policy(client, created_emails, email, ["permissions:grant"], resource_type="permissions")

    resp = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{"user_email": email, "action": "users:delete_any", "resource_type": "users"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 0
    assert body["error_count"] == 1
    assert body["results"][0]["status"] == "error"

    list_resp = await client.get("/authorization/users/me/permissions")
    assert list_resp.json()["permissions"] == []


@pytest.mark.asyncio
async def test_bulk_permissions_assign_applies_valid_items_even_when_one_item_attempts_escalation(
    client, created_emails
):
    """One batch item is an escalation attempt (denied), the other is a
    legitimate grant of an action the caller already holds (allowed): the
    per-item guard shouldn't fail the whole batch."""
    email = unique_email("bulk-mixed-escalate")
    # Two policies, since each is scoped to one resource_type: permissions:grant
    # on "permissions" (route-level gate) and users:list_all on "users"
    # (what the second item grants, which the caller must already hold).
    grant_policy_name = unique_policy_name()
    list_all_policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": grant_policy_name, "actions": ["permissions:grant"], "resource_type": "permissions", "conditions": None},
            session,
        )
        await policy_repository.create(
            {"name": list_all_policy_name, "actions": ["users:list_all"], "resource_type": "users", "conditions": None},
            session,
        )
    await create_verified_user(
        client, created_emails, email, [SELF_SERVICE_POLICY_NAME, grant_policy_name, list_all_policy_name]
    )

    resp = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [
            {"user_email": email, "action": "users:delete_any", "resource_type": "users"},
            {"user_email": email, "action": "users:list_all", "resource_type": "users"},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    outcomes = {(r["identifier"]): r["status"] for r in body["results"]}
    assert outcomes["users:delete_any"] == "error"
    assert outcomes["users:list_all"] == "success"


@pytest.mark.asyncio
async def test_bulk_permissions_assign_forwards_the_items_own_conditions_to_the_grant_guard(
    client, created_emails
):
    """Regression: bulk_permission_routes.py used to call
    assert_authorized_to_grant without forwarding the item's own
    `conditions`, so assert_authorized_to_grant always evaluated as if a
    fully unconditional grant were being proposed (see its `conditions`
    parameter's default). For a caller who holds an action only through a
    network-restricted policy, that made assert_authorized_to_grant compare
    "caller holds this only within 127.0.0.1/network" against "proposal is
    unconditional" and reject with CANNOT_GRANT_BROADER_CONDITIONS - even
    when the bulk item asked for that caller's own exact, narrower scope,
    not a broader one. Fixed by threading conditions=item.conditions
    through. This proves the bulk HTTP route wiring itself preserves a
    legitimate narrow grant, not just the guard function in isolation (see
    test_authorization_grant_guard_context_unit.py for that)."""
    grant_policy_name = unique_policy_name()
    narrow_list_all_policy_name = unique_policy_name()
    narrow_conditions = {"network": {"allowed_ips": ["127.0.0.1"]}}
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": grant_policy_name, "actions": ["permissions:grant"], "resource_type": "permissions", "conditions": None},
            session,
        )
        await policy_repository.create(
            {
                "name": narrow_list_all_policy_name,
                "actions": ["users:list_all"],
                "resource_type": "users",
                # 127.0.0.1, not some arbitrary office range: httpx's
                # ASGITransport reports every test request's real peer as
                # 127.0.0.1 (see test_context_spoofing_security.py's own
                # comment), so this is the caller's actual connecting IP -
                # required for their own grant to evaluate as held at all
                # before the conditions-preserved check below even runs.
                "conditions": narrow_conditions,
            },
            session,
        )
    email = unique_email("bulk-narrow-grant")
    await create_verified_user(
        client, created_emails, email, [SELF_SERVICE_POLICY_NAME, grant_policy_name, narrow_list_all_policy_name]
    )

    target_email = unique_email("bulk-narrow-target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    resp = await client.post(
        "/authorization/bulk/permissions/assign",
        json={"items": [{
            "user_email": target_email, "action": "users:list_all", "resource_type": "users",
            "conditions": narrow_conditions,
        }]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["results"][0]["status"] == "success"

    async with database.async_session() as session:
        target_grants = await user_permission_repository.get_permissions_for_user(target_email, session)
    matching = [g for g in target_grants if g.action == "users:list_all" and g.resource_type == "users"]
    assert len(matching) == 1
    assert matching[0].conditions == narrow_conditions


@pytest.mark.asyncio
async def test_system_superuser_can_still_grant_permissions(client, created_emails):
    """Negative control, same as the policies:assign equivalent: a genuine
    system_superuser holder is not blocked by the same guard."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    target_email = unique_email("grant-target")
    await create_user_with_custom_policy(client, created_emails, target_email, [], resource_type="users")

    # create_user_with_custom_policy leaves `client` logged in as the
    # target: switch back to the actual system_superuser caller before
    # making the grant request under test.
    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})

    resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "users:delete_any", "resource_type": "users"},
    )
    assert resp.status_code == 200
