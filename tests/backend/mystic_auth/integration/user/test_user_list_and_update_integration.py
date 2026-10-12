# tests/backend/mystic_auth/integration/user/test_user_list_and_update_integration.py
#
# End-to-end PBAC coverage for the GET /users/ authorization gate and the
# core PBAC claims: role is metadata only and never consulted for access,
# and roleless accounts still work. Admin-side listing/filtering/sorting
# and admin-driven updates live in test_user_admin_management_integration.py;
# delete/purge/reactivate and password-change side effects live in
# test_user_account_lifecycle_integration.py.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from backend.mystic_auth.user.user_model import UserRole

from .user_test_accounts import (
    PASSWORD,
    create_roleless_user,
    create_verified_user,
    unique_email,
)

# ---------------------------- Unauthenticated access ----------------------------

@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/users/")
    assert resp.status_code == 401


# ---------------------------- Regular user is not an admin ----------------------------

@pytest.mark.asyncio
async def test_regular_user_cannot_list_all_users(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    resp = await client.get("/users/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_update_another_user(client, created_emails):
    email = unique_email()
    other_email = unique_email("other")
    await create_verified_user(client, created_emails, other_email)
    await create_verified_user(client, created_emails, email)

    resp = await client.put(f"/users/{other_email}", json={"name": "Hacked"})
    assert resp.status_code == 403


# ---------------------------- Core PBAC claims ----------------------------
# Proves identical roles can have different permissions, and that policies
# (not roles) determine access.

@pytest.mark.asyncio
async def test_identical_roles_can_have_different_permissions(client, created_emails):
    admin_with_access_email = unique_email("admin-full")
    admin_without_access_email = unique_email("admin-bare")

    # Both accounts carry role=admin...
    await create_verified_user(
        client, created_emails, admin_with_access_email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME],
    )
    await create_verified_user(
        client, created_emails, admin_without_access_email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME],  # no user_management policy
    )

    # ...but only the one actually holding user_management can list users.
    with_access_resp = await client.post(
        "/auth/login", json={"email": admin_with_access_email, "password": PASSWORD}
    )
    assert with_access_resp.status_code == 200
    listed = await client.get("/users/")
    assert listed.status_code == 200

    without_access_resp = await client.post(
        "/auth/login", json={"email": admin_without_access_email, "password": PASSWORD}
    )
    assert without_access_resp.status_code == 200
    denied = await client.get("/users/")
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_a_plain_role_user_with_admin_policy_gets_admin_capability(client, created_emails):
    # The converse: role="user" with user_management assigned directly
    # must be authorized exactly like an "admin"-role account.
    email = unique_email()
    await create_verified_user(
        client, created_emails, email,
        role=UserRole.user,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME],
    )

    resp = await client.get("/users/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_all_users_respects_limit_query_param(client, created_emails):
    # Regression guard: GET /users/ previously read the whole table
    # unconditionally, unlike every other list endpoint in the app.
    email = unique_email()
    await create_verified_user(
        client, created_emails, email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME],
    )
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    resp = await client.get("/users/?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------- Users without roles ----------------------------
# role is nullable so a roleless account can still authenticate and be
# authorized purely via its assigned policies, with no role fallback.

@pytest.mark.asyncio
async def test_roleless_user_gets_admin_level_access_when_assigned_admin_policies(client, created_emails):
    # A roleless account isn't capped at "basic" access: it gets whatever
    # policies it holds, same as any role-carrying account.
    email = unique_email("roleless-admin")
    await create_roleless_user(
        created_emails, email, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME]
    )

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get("/users/")
    assert resp.status_code == 200
