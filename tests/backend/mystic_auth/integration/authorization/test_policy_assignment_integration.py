# tests/backend/mystic_auth/integration/test_policy_assignment_integration.py
#
# End-to-end coverage for policy_assignment_routes.py (backend/mystic_auth/
# api/pbac_routes/) against the real ASGI app, real PostgreSQL, and real
# Valkey. Split out of what used to be one 568-line
# test_authorization_routes_integration.py. Proves that assigning/removing a
# policy via this API actually changes what an account can do (the real
# end-to-end point of the whole system), not just that the DB row changed.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
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


@pytest.mark.asyncio
async def test_assigning_user_management_via_the_api_actually_grants_list_all_access(
    client, created_emails
):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    # Before assignment: target cannot list users. Log in as target to check.
    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    denied = await client.get("/users/")
    assert denied.status_code == 403

    # Assign, acting as the system user
    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assign_resp = await client.post(
        f"/authorization/users/{target_email}/policies",
        json={"policy_name": USER_MANAGEMENT_POLICY_NAME},
    )
    assert assign_resp.status_code == 200

    # After assignment: target can list users, no new login/token needed,
    # since authorization is evaluated fresh from the DB on every request.
    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    allowed = await client.get("/users/")
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_removing_a_policy_via_the_api_actually_revokes_access(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(
        client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME]
    )
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    allowed = await client.get("/users/")
    assert allowed.status_code == 200

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    remove_resp = await client.delete(
        f"/authorization/users/{target_email}/policies/{USER_MANAGEMENT_POLICY_NAME}"
    )
    assert remove_resp.status_code == 200

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    denied = await client.get("/users/")
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_removing_a_policy_the_user_does_not_hold_returns_404(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    resp = await client.delete(
        f"/authorization/users/{target_email}/policies/{USER_MANAGEMENT_POLICY_NAME}"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_user_policies_reports_currently_assigned_policies(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(
        client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME]
    )
    await create_system_user(client, created_emails, system_email)

    resp = await client.get(f"/authorization/users/{target_email}/policies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == target_email
    names = {p["name"] for p in body["policies"]}
    assert names == {SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME}


@pytest.mark.asyncio
async def test_users_me_policies_returns_the_callers_own_policies_without_policies_read(
    client, created_emails
):
    """The frontend's getUserPolicies() calls this self-service endpoint:
    a plain self_service-only user (no policies:read) must be able to see
    their own assignments, unlike the admin GET /users/{email}/policies."""
    email = unique_email()
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/users/me/policies")

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == email
    names = {p["name"] for p in body["policies"]}
    assert names == {SELF_SERVICE_POLICY_NAME}


@pytest.mark.asyncio
async def test_users_me_policies_is_not_shadowed_by_the_admin_route(client, created_emails):
    """Registration-order regression guard: /users/me/policies must not be
    swallowed by /users/{user_email}/policies (which would otherwise try
    to look up a real user named "me" and 404, or require policies:read)."""
    email = unique_email()
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/users/me/policies")

    assert resp.status_code == 200
    assert resp.json()["user_email"] == email  # never the literal string "me"


@pytest.mark.asyncio
async def test_list_policy_holders_returns_every_assigned_user(client, created_emails):
    """GET /policies/{name}/holders backs the frontend's "Assigned users"
    dialog and the delete confirm's holder count."""
    system_email = unique_email("system")
    holder_a = unique_email("holder-a")
    holder_b = unique_email("holder-b")
    policy_name = unique_policy_name()
    await create_system_user(client, created_emails, system_email)

    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": ["users:read"], "resource_type": "users", "conditions": None},
            session,
        )

    await create_verified_user(client, created_emails, holder_a, [SELF_SERVICE_POLICY_NAME, policy_name])
    await create_verified_user(client, created_emails, holder_b, [SELF_SERVICE_POLICY_NAME, policy_name])

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.get(f"/authorization/policies/{policy_name}/holders")

    assert resp.status_code == 200
    holders = resp.json()
    emails = {h["email"] for h in holders}
    assert emails == {holder_a, holder_b}
    for holder in holders:
        assert holder["name"]
        assert holder["assigned_at"]


@pytest.mark.asyncio
async def test_list_policy_holders_returns_empty_list_for_unassigned_policy(client, created_emails):
    system_email = unique_email("system")
    policy_name = unique_policy_name()
    await create_system_user(client, created_emails, system_email)

    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": ["users:read"], "resource_type": "users", "conditions": None},
            session,
        )

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.get(f"/authorization/policies/{policy_name}/holders")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_policy_holders_404s_for_unknown_policy(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.get("/authorization/policies/does_not_exist/holders")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_policy_holders_requires_policies_read(client, created_emails):
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": ["users:read"], "resource_type": "users", "conditions": None},
            session,
        )

    viewer_email = unique_email("no-read")
    await create_verified_user(client, created_emails, viewer_email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get(f"/authorization/policies/{policy_name}/holders")

    assert resp.status_code == 403
