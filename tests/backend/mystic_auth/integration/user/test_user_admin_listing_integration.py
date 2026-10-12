# tests/backend/mystic_auth/integration/user/test_user_admin_listing_integration.py
#
# End-to-end coverage for admin-side GET /users/ listing/filtering/sorting
# (user_management_query_routes.py), against the real ASGI app, real
# PostgreSQL, and real Valkey (see conftest.py). Split out of
# test_user_admin_management_integration.py once that file passed the
# repo's file-length guideline; see that file for PUT /users/{email},
# PATCH /users/{email}/role, and the system-user guards.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)

from .user_test_accounts import (
    PASSWORD,
    create_admin,
    create_system_user,
    create_verified_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_admin_can_list_all_users(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    resp = await client.get("/users/")
    assert resp.status_code == 200
    assert any(u["email"] == admin_email for u in resp.json())


@pytest.mark.asyncio
async def test_list_all_users_reports_total_count_via_header(client, created_emails):
    """X-Total-Count (used by UsersPage.tsx for numbered pagination) must
    reflect the true total, not just how many rows this page returned."""
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    full_resp = await client.get("/users/")
    total = int(full_resp.headers["x-total-count"])
    assert total == len(full_resp.json())

    limited_resp = await client.get("/users/", params={"limit": 1})
    # X-Total-Count describes the whole result set, not this one page, so
    # it stays the same regardless of the page size requested.
    assert int(limited_resp.headers["x-total-count"]) == total
    assert len(limited_resp.json()) == 1


@pytest.mark.asyncio
async def test_list_all_users_search_filters_by_name_or_email(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    target_email = unique_email("findme")
    # create_verified_user leaves the client logged in as target_email, so
    # log back in as admin before querying the list.
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
async def test_list_all_users_filters_by_policy_name(client, created_emails):
    # create_admin holds user_management; create_verified_user's
    # default policy (self_service only) doesn't.
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    plain_email = unique_email("plainuser")
    await create_verified_user(client, created_emails, plain_email)
    login_resp = await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get("/users/", params={"policy": USER_MANAGEMENT_POLICY_NAME})
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert admin_email in emails
    assert plain_email not in emails

    self_service_only = await client.get(
        "/users/", params={"policy": SELF_SERVICE_POLICY_NAME, "search": plain_email.split("@")[0]}
    )
    assert self_service_only.status_code == 200
    assert plain_email in [u["email"] for u in self_service_only.json()]


@pytest.mark.asyncio
async def test_list_all_users_filters_by_permission(client, created_emails):
    # users:list_all comes from user_management, not self_service, so
    # this proves the filter matches on the policy's actions, not its name.
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    plain_email = unique_email("plainuser")
    await create_verified_user(client, created_emails, plain_email)
    login_resp = await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get("/users/", params={"permission": "users:list_all", "permission_source": "policy"})
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert admin_email in emails
    assert plain_email not in emails
    assert int(resp.headers["x-total-count"]) == len(resp.json())


@pytest.mark.asyncio
async def test_list_all_users_filters_by_permission_includes_a_direct_grant_holder(client, created_emails):
    """A permission can be held two ways: through a policy (covered by
    test_list_all_users_filters_by_permission above), or as a direct
    UserPermission grant that bypasses Policy entirely (POST
    /authorization/users/{email}/permissions). Both are genuinely effective
    grants, so the filter must also surface a user who holds it only the
    direct-grant way."""
    # The granter needs permissions:grant (only system_superuser has it),
    # which also happens to grant rate_limits:read, so system_email is used
    # only to perform the grant and the query, never asserted on below.
    # admin_email (user_management only, no rate_limits:read via any
    # policy) is the "should not appear" control instead.
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    direct_grant_email = unique_email("directgrant")
    # self_service only: no policy grants rate_limits:read, so this user
    # would be invisible to the filter without the direct-grant branch.
    await create_verified_user(client, created_emails, direct_grant_email)

    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200
    grant_resp = await client.post(
        f"/authorization/users/{direct_grant_email}/permissions",
        json={"action": "rate_limits:read", "resource_type": "rate_limits"},
    )
    assert grant_resp.status_code == 200

    resp = await client.get(
        "/users/", params={"permission": "rate_limits:read", "permission_source": "direct"}
    )
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert direct_grant_email in emails
    assert admin_email not in emails
    assert int(resp.headers["x-total-count"]) == len(resp.json())


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
