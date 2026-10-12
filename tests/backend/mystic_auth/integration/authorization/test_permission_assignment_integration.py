# tests/backend/mystic_auth/integration/authorization/test_permission_assignment_integration.py
#
# End-to-end coverage for permission_assignment_routes.py (backend/mystic_auth/
# api/pbac_routes/): direct, single-action grants to a user that bypass
# Policy entirely (see authorization/models/user_permission_model.py).
# Mirrors test_policy_assignment_integration.py's shape - same real ASGI
# app, real PostgreSQL, real Valkey - proving a direct grant/revoke actually
# changes what an account can do, not just that a row changed.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)

from .authorization_test_accounts import (
    PASSWORD,
    create_system_user,
    create_verified_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_granting_a_direct_permission_actually_grants_access(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    # Before the grant: target cannot list users (no policy grants users:list_all).
    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    denied = await client.get("/users/")
    assert denied.status_code == 403

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "users:list_all", "resource_type": "users"},
    )
    assert grant_resp.status_code == 200

    # After the grant: target can list users - authorization is evaluated
    # fresh from the DB (direct grants normalized into the same evaluation
    # path as policies, see AuthorizationService._get_effective_policies),
    # no new login/token needed.
    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    allowed = await client.get("/users/")
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_auth_me_permissions_includes_a_direct_grant_with_no_matching_policy(client, created_emails):
    """GET /auth/me is what every frontend IfCan/ProtectedRoute check reads
    (see current_user_handler.py) - a direct grant must show up there
    exactly like the request above proves it shows up in real enforcement,
    or a caller granted only a direct permission (no Policy at all covers
    it) would pass every real authorization check yet see none of the
    corresponding UI."""
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "policies:create", "resource_type": "policies"},
    )
    assert grant_resp.status_code == 200

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    me_resp = await client.get("/auth/me")

    assert me_resp.status_code == 200
    assert "policies:create" in me_resp.json()["permissions"]


@pytest.mark.asyncio
async def test_revoking_a_direct_permission_actually_revokes_access(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "users:list_all", "resource_type": "users"},
    )
    assert grant_resp.status_code == 200

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    allowed = await client.get("/users/")
    assert allowed.status_code == 200

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    revoke_resp = await client.delete(
        f"/authorization/users/{target_email}/permissions/users:list_all",
        params={"resource_type": "users"},
    )
    assert revoke_resp.status_code == 200

    # Immediately, not after the 60s cache TTL: revoke must precisely
    # invalidate authz:user_permissions:{email}, same as policy revoke does
    # for authz:user_policies:{email}.
    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    denied = await client.get("/users/")
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_revoking_a_permission_not_held_returns_404(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    resp = await client.delete(
        f"/authorization/users/{target_email}/permissions/users:list_all",
        params={"resource_type": "users"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_re_granting_the_same_action_updates_conditions_in_place(client, created_emails):
    """Direct grants are idempotent on (action, resource_type) but, unlike
    assign_policy_to_user's pure no-op, update `conditions` in place - a
    grant's conditions are supplied per-assignment, so re-granting with
    different conditions is how you change an existing grant's scope."""
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    first = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "users:list_all", "resource_type": "users", "conditions": {"self_only": True}},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "users:list_all", "resource_type": "users"},
    )
    assert second.status_code == 200

    list_resp = await client.get(f"/authorization/users/{target_email}/permissions")
    assert list_resp.status_code == 200
    grants = list_resp.json()["permissions"]
    assert len(grants) == 1  # updated in place, not a second row
    assert grants[0]["conditions"] is None


@pytest.mark.asyncio
async def test_list_user_permissions_reports_currently_granted_permissions(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "users:list_all", "resource_type": "users"},
    )

    resp = await client.get(f"/authorization/users/{target_email}/permissions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == target_email
    actions = {p["action"] for p in body["permissions"]}
    assert actions == {"users:list_all"}


@pytest.mark.asyncio
async def test_users_me_permissions_returns_the_callers_own_grants_without_permissions_read(
    client, created_emails
):
    system_email = unique_email("system")
    email = unique_email()
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    await client.post(
        f"/authorization/users/{email}/permissions",
        json={"action": "users:list_all", "resource_type": "users"},
    )

    # A plain self_service-only user (no permissions:read) must still see
    # their own grants, mirroring /authorization/users/me/policies.
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    resp = await client.get("/authorization/users/me/permissions")

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == email
    assert {p["action"] for p in body["permissions"]} == {"users:list_all"}


@pytest.mark.asyncio
async def test_users_me_permissions_is_not_shadowed_by_the_admin_route(client, created_emails):
    """Registration-order regression guard, same as the policies equivalent:
    /users/me/permissions must not be swallowed by
    /users/{user_email}/permissions."""
    email = unique_email()
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/users/me/permissions")

    assert resp.status_code == 200
    assert resp.json()["user_email"] == email
