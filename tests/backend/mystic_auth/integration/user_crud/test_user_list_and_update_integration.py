# tests/backend/mystic_auth/integration/test_user_list_and_update_integration.py
#
# End-to-end PBAC coverage for the authorization gate, GET /users/stats,
# GET /users/ (list/filter/sort), PUT /users/{email}, and PATCH /users/
# {email}/role (user_management_query_routes.py / user_management_update_routes.py)
# against the real ASGI app, real
# PostgreSQL, and real Redis (see conftest.py). Split out of what used to be
# one 629-line test_user_management_routes_integration.py: this half covers
# viewing/editing an existing account; test_user_account_lifecycle_
# integration.py covers delete/purge/reactivate and password-change
# side effects. Authorization here is entirely policy-driven (see
# authorization/): role is metadata only and is never consulted to decide
# what a caller may do: these tests prove that directly (see "identical
# roles, different permissions" below), not just that the previously-
# RBAC-era route behavior still holds.
import pytest
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user_crud.user_crud_collector import user_crud
from backend.mystic_auth.user_table.user_model import UserRole

from .user_test_accounts import (
    PASSWORD,
    create_admin,
    create_roleless_user,
    create_system_user,
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
# Per the PBAC testing requirements: prove that identical roles can have
# different permissions, and that policies (not roles) determine access.

@pytest.mark.asyncio
async def test_identical_roles_can_have_different_permissions(client, created_emails):
    admin_with_access_email = unique_email("admin-full")
    admin_without_access_email = unique_email("admin-bare")

    # Both accounts carry role=admin (identical metadata)...
    await create_verified_user(
        client, created_emails, admin_with_access_email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME],
    )
    await create_verified_user(
        client, created_emails, admin_without_access_email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME],  # no user_administration policy
    )

    # ...but only the one actually holding user_administration can list users.
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
    # The converse: role="user" (the lowest metadata tier) with
    # user_administration assigned directly must be authorized exactly like
    # an "admin"-role account: role plays no part in the decision at all.
    email = unique_email()
    await create_verified_user(
        client, created_emails, email,
        role=UserRole.user,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME],
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
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME],
    )
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    resp = await client.get("/users/?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------- Users without roles ----------------------------
# Per the role-as-metadata invariant: "The system must support ... users
# without roles", and Testing Requirements: "users without roles still
# work". role is nullable precisely so this is possible (see
# user_model.py): a roleless account must still authenticate (real login,
# real JWT, real GET /auth/me) and be authorized purely via its assigned
# policies, with no fallback to any role-based behavior anywhere.

@pytest.mark.asyncio
async def test_roleless_user_gets_admin_level_access_when_assigned_admin_policies(client, created_emails):
    # The strongest form of the claim: a roleless account isn't capped at
    # "basic" access: it gets exactly whatever policies it holds, same as
    # any role-carrying account, proving role never enters the decision.
    email = unique_email("roleless-admin")
    await create_roleless_user(
        created_emails, email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME]
    )

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get("/users/")
    assert resp.status_code == 200


# ---------------------------- Admin privileges ----------------------------

@pytest.mark.asyncio
async def test_admin_can_list_all_users(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    resp = await client.get("/users/")
    assert resp.status_code == 200
    assert any(u["email"] == admin_email for u in resp.json())


@pytest.mark.asyncio
async def test_list_all_users_reports_total_count_via_header(client, created_emails):
    """X-Total-Count (UsersPage.tsx's numbered-pagination page count) must
    reflect the true total, not just how many rows this one page returned."""
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    full_resp = await client.get("/users/")
    total = int(full_resp.headers["x-total-count"])
    assert total == len(full_resp.json())

    limited_resp = await client.get("/users/", params={"limit": 1})
    # Same total regardless of the page size requested: X-Total-Count
    # describes the whole result set, not this one page.
    assert int(limited_resp.headers["x-total-count"]) == total
    assert len(limited_resp.json()) == 1


@pytest.mark.asyncio
async def test_list_all_users_search_filters_by_name_or_email(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    target_email = unique_email("findme")
    # Ends logged in as target_email, so switch back to the admin
    # afterwards to actually query the list.
    await create_verified_user(client, created_emails, target_email)
    login_resp = await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get("/users/", params={"search": target_email.split("@")[0]})
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert target_email in emails
    assert admin_email not in emails
    assert int(resp.headers["x-total-count"]) == 1


@pytest.mark.asyncio
async def test_list_all_users_filters_by_role_and_is_verified(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    plain_email = unique_email("plainuser")
    await create_verified_user(client, created_emails, plain_email)
    login_resp = await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    admin_only = await client.get("/users/", params={"role": "admin", "is_verified": "true"})
    assert admin_only.status_code == 200
    admin_only_emails = [u["email"] for u in admin_only.json()]
    assert admin_email in admin_only_emails
    assert plain_email not in admin_only_emails
    assert all(u["role"] == "admin" for u in admin_only.json())

    user_only = await client.get("/users/", params={"role": "user"})
    assert user_only.status_code == 200
    user_only_emails = [u["email"] for u in user_only.json()]
    assert plain_email in user_only_emails
    assert admin_email not in user_only_emails


@pytest.mark.asyncio
async def test_list_all_users_filters_by_status(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    deleted_email = unique_email("softdeleted")
    await create_verified_user(client, created_emails, deleted_email)

    login_resp = await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    assert login_resp.status_code == 200
    delete_resp = await client.delete(f"/users/{deleted_email}")
    assert delete_resp.status_code == 200

    deleted_only = await client.get("/users/", params={"status": "deleted", "search": deleted_email.split("@")[0]})
    assert deleted_only.status_code == 200
    deleted_emails = [u["email"] for u in deleted_only.json()]
    assert deleted_email in deleted_emails

    active_only = await client.get("/users/", params={"status": "active", "search": deleted_email.split("@")[0]})
    assert active_only.status_code == 200
    assert deleted_email not in [u["email"] for u in active_only.json()]


@pytest.mark.asyncio
async def test_list_all_users_sort_by_email(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    prefix = unique_email("sorttest").split("@")[0]
    email_a = f"{prefix}-aaa@example.com"
    email_b = f"{prefix}-bbb@example.com"
    await create_verified_user(client, created_emails, email_b)
    await create_verified_user(client, created_emails, email_a)

    login_resp = await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get(
        "/users/", params={"search": prefix, "sort_by": "email", "sort_dir": "asc"}
    )
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert emails == sorted(emails)
    assert emails.index(email_a) < emails.index(email_b)


@pytest.mark.asyncio
async def test_admin_can_update_a_regular_user(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")

    # Create the target as its own session first so logging in as the
    # admin afterwards doesn't affect it.
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"name": "Renamed By Admin"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed By Admin"


@pytest.mark.asyncio
async def test_admin_cannot_modify_system_user(client, created_emails):
    # Regression test for the privilege-escalation gap where update_any_user
    # lacked the system-user guard present on delete/role-update: an admin
    # could PUT a new password onto the system account and take it over
    # entirely. This guard is a target-resource invariant, not a PBAC
    # decision; see user_management_update_routes.py's UserRole import note.
    admin_email = unique_email("admin")
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{system_email}", json={"password": "NewPass123!"})
    assert resp.status_code == 403

    # The system account's password must be unchanged: verify by logging
    # in with the original password.
    login_resp = await client.post(
        "/auth/login", json={"email": system_email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_delete_system_user(client, created_emails):
    admin_email = unique_email("admin")
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{system_email}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_change_system_user_role(client, created_emails):
    admin_email = unique_email("admin")
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{system_email}/role", json={"role": "user"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_assign_system_role_to_another_user(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "system"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_change_user_role_to_admin_and_back_via_role_endpoint(client, created_emails):
    # Role changes are bidirectional through the single generic /role
    # endpoint; there is no separate one-directional "promote" path. An
    # admin holding only user_administration (which grants users:assign_role,
    # not users:assign_system_role) can move a non-system user to any
    # non-system role, in either direction.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "admin"})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.role == UserRole.admin

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "user"})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.role == UserRole.user
