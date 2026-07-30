# tests/backend/mystic_auth/integration/test_user_routes_integration.py
#
# End-to-end PBAC coverage for /users/* against the real ASGI app, real
# PostgreSQL, and real Redis (see conftest.py). Authorization here is
# entirely policy-driven (see authorization/): role is metadata only and
# is never consulted to decide what a caller may do: these tests prove
# that directly (see "identical roles, different permissions" below),
# not just that the previously-RBAC-era route behavior still holds.
import uuid

import pytest
from backend.mystic_auth.auth.password_logic.password_service import password_service
from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import policy_repository
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from backend.mystic_auth.user_crud.user_crud_collector import user_crud
from backend.mystic_auth.user_table.user_model import UserRole

PASSWORD = "StrongPass123!"


def _unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


# conftest.py's `client` fixture uses base_url="https://testserver", a
# dotless hostname, which CPython's http.cookiejar (what httpx's cookie jar
# is built on) normalizes to "testserver.local" internally for matching
# purposes. Cookies set manually here must match that (domain, path, name)
# key exactly, or they land as a second, separate jar entry instead of
# overwriting the real one from a prior response, see
# _post_with_refresh_cookie's docstring below for why that matters.
_TEST_COOKIE_DOMAIN = "testserver.local"


async def _post_with_refresh_cookie(client, url: str, refresh_token: str):
    """Posts to a refresh_token-cookie-gated endpoint with an explicit cookie
    value, independent of whatever the client's shared cookie jar currently
    holds, needed to simulate stale/reused/forged/cross-session tokens.
    httpx deprecated per-request `cookies=` in favor of setting cookies on
    the client itself, hence setting it here rather than passing `cookies=`.
    Both domain and path must match the real cookie's (see
    _TEST_COOKIE_DOMAIN above): the jar keys cookies by (domain, path,
    name), so an inexact match creates a second entry alongside the real one
    instead of overwriting it, which then survives the endpoint's own
    cookie-clearing response untouched."""
    client.cookies.set("refresh_token", refresh_token, domain=_TEST_COOKIE_DOMAIN, path="/auth")
    return await client.post(url)


async def _assign_policies(email: str, policy_names: list[str]) -> None:
    """Grants real capability the same way the policy management API
    would (see backend/mystic_auth/api/pbac_routes/policy_assignment_routes.py):
    this is the ONLY thing that determines what an account can do under PBAC."""
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id, policy_id=policy.id, db=session, assigned_by="test"
            )


async def _create_verified_user(
    client, created_emails, email: str, role: UserRole = UserRole.user, policy_names: list[str] | None = None
):
    """Signs up and verifies a user. `role` is set purely as display/
    grouping metadata (and, for system_email, to trigger the target-account
    protection invariant in user_routes.py; see its module docstring for
    why that's not an authorization decision). `policy_names` is what
    actually grants capability; defaults to just self_service, mirroring
    what real signup does (see signup_service.py)."""
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    if role != UserRole.user:
        async with database.async_session() as session:
            user = await user_crud.get_by_email(email, session)
            await user_crud.update_role(user, role, session)

    await _assign_policies(email, policy_names if policy_names is not None else [SELF_SERVICE_POLICY_NAME])

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return login_resp


async def _create_admin(client, created_emails, email: str):
    return await _create_verified_user(
        client, created_emails, email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME],
    )


async def _create_system_user(client, created_emails, email: str):
    return await _create_verified_user(
        client, created_emails, email,
        role=UserRole.system,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


# ---------------------------- Unauthenticated access ----------------------------

@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/users/")
    assert resp.status_code == 401


# ---------------------------- Regular user is not an admin ----------------------------

@pytest.mark.asyncio
async def test_regular_user_cannot_list_all_users(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    resp = await client.get("/users/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_update_another_user(client, created_emails):
    email = _unique_email()
    other_email = _unique_email("other")
    await _create_verified_user(client, created_emails, other_email)
    await _create_verified_user(client, created_emails, email)

    resp = await client.put(f"/users/{other_email}", json={"name": "Hacked"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_can_update_own_profile(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    resp = await client.put("/users/me", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


# ---------------------------- Core PBAC claims ----------------------------
# Per claude.md's Testing Requirements: prove that identical roles can have
# different permissions, and that policies (not roles) determine access.

@pytest.mark.asyncio
async def test_identical_roles_can_have_different_permissions(client, created_emails):
    admin_with_access_email = _unique_email("admin-full")
    admin_without_access_email = _unique_email("admin-bare")

    # Both accounts carry role=admin (identical metadata)...
    await _create_verified_user(
        client, created_emails, admin_with_access_email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME],
    )
    await _create_verified_user(
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
    email = _unique_email()
    await _create_verified_user(
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
    email = _unique_email()
    await _create_verified_user(
        client, created_emails, email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME],
    )
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    resp = await client.get("/users/?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------- Users without roles ----------------------------
# Per claude.md's "Roles" section: "The system must support ... users
# without roles", and Testing Requirements: "users without roles still
# work". role is nullable precisely so this is possible (see
# user_model.py): a roleless account must still authenticate (real login,
# real JWT, real GET /auth/me) and be authorized purely via its assigned
# policies, with no fallback to any role-based behavior anywhere.

async def _create_roleless_user(created_emails, email: str, policy_names: list[str]) -> None:
    """Creates a fully real, loggable-in account with role=None directly
    (signup_service always sets role="user" for display purposes, so a
    genuinely roleless account can only be produced this way today; there
    is no API to clear an existing role, which is out of scope here)."""
    async with database.async_session() as session:
        hashed_password = await password_service.hash_password(PASSWORD)
        user = await user_crud.create({
            "name": "Roleless User",
            "email": email,
            "hashed_password": hashed_password,
            "role": None,
            "is_verified": True,
            "is_active": True,
        }, session)
        created_emails.append(email)

        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id, policy_id=policy.id, db=session, assigned_by="test"
            )


@pytest.mark.asyncio
async def test_roleless_user_can_authenticate_and_use_self_service(client, created_emails):
    email = _unique_email("roleless")
    await _create_roleless_user(created_emails, email, [SELF_SERVICE_POLICY_NAME])

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    me_resp = await client.get("/auth/me")
    assert me_resp.status_code == 200
    me_body = me_resp.json()
    assert me_body["role"] is None
    assert me_body["permissions"] == ["users:read_own", "users:update_own"]

    profile_resp = await client.get("/users/me")
    assert profile_resp.status_code == 200
    assert profile_resp.json()["role"] is None


@pytest.mark.asyncio
async def test_roleless_user_gets_admin_level_access_when_assigned_admin_policies(client, created_emails):
    # The strongest form of the claim: a roleless account isn't capped at
    # "basic" access: it gets exactly whatever policies it holds, same as
    # any role-carrying account, proving role never enters the decision.
    email = _unique_email("roleless-admin")
    await _create_roleless_user(
        created_emails, email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME]
    )

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get("/users/")
    assert resp.status_code == 200


# ---------------------------- Admin privileges ----------------------------

@pytest.mark.asyncio
async def test_admin_can_list_all_users(client, created_emails):
    admin_email = _unique_email("admin")
    await _create_admin(client, created_emails, admin_email)

    resp = await client.get("/users/")
    assert resp.status_code == 200
    assert any(u["email"] == admin_email for u in resp.json())


@pytest.mark.asyncio
async def test_admin_can_update_a_regular_user(client, created_emails):
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")

    # Create the target as its own session first so logging in as the
    # admin afterwards doesn't affect it.
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"name": "Renamed By Admin"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed By Admin"


@pytest.mark.asyncio
async def test_admin_cannot_modify_system_user(client, created_emails):
    # Regression test for the privilege-escalation gap where update_any_user
    # lacked the system-user guard present on delete/role-update: an admin
    # could PUT a new password onto the system account and take it over
    # entirely. This guard is a target-resource invariant, not a PBAC
    # decision; see user_routes.py's UserRole import note.
    admin_email = _unique_email("admin")
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    await _create_admin(client, created_emails, admin_email)

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
    admin_email = _unique_email("admin")
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{system_email}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_change_system_user_role(client, created_emails):
    admin_email = _unique_email("admin")
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{system_email}/role", json={"role": "user"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_assign_system_role_to_another_user(client, created_emails):
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "system"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_change_user_role_to_admin_and_back_via_role_endpoint(client, created_emails):
    # Role changes are bidirectional through the single generic /role
    # endpoint; there is no separate one-directional "promote" path. An
    # admin holding only user_administration (which grants users:assign_role,
    # not users:assign_system_role) can move a non-system user to any
    # non-system role, in either direction.
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

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


# ---------------------------- System privileges ----------------------------


@pytest.mark.asyncio
async def test_system_user_can_assign_system_role(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_system_user(client, created_emails, system_email)

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "system"})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.role == UserRole.system


# ---------------------------- Account lifecycle: soft delete / purge / reactivate ----------------------------

@pytest.mark.asyncio
async def test_admin_delete_soft_deletes_a_user(client, created_emails):
    # DELETE /users/{email} is the default, reversible deletion flow: the
    # row survives (preserving audit history / FK-referencing rows) with
    # is_active=False + deleted_at set, not a hard delete.
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user is not None  # row still exists, this is a soft delete
        assert user.is_active is False
        assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_deleted_user_cannot_login(client, created_emails):
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    login_resp = await client.post(
        "/auth/login", json={"email": target_email, "password": PASSWORD}
    )
    assert login_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_soft_delete_revokes_the_deleted_users_active_session(client, created_emails):
    # A deleted account's existing refresh token must stop working
    # immediately, not just "eventually, once it expires on its own"; see
    # delete_any_user's Step 4 in user_routes.py.
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    # Capture the just-logged-in target user's own refresh token before the
    # shared client's cookie jar gets overwritten by the admin login below.
    target_refresh_token = client.cookies.get("refresh_token")
    assert target_refresh_token

    await _create_admin(client, created_emails, admin_email)  # overwrites the client's cookie jar

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    # The deleted user's OLD refresh token, presented independently of the
    # (now admin-owned) cookie jar, must be rejected.
    refresh_resp = await _post_with_refresh_cookie(client, "/auth/refresh/", target_refresh_token)
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_self_password_change_revokes_existing_sessions(client, created_emails):
    # Regression guard: changing a password via PUT /users/me previously left
    # every existing session alive, unlike password_reset_service.py's
    # equivalent flow (which explicitly revokes on the theory that a
    # password change may be happening because the account is compromised).
    email = _unique_email()
    login_resp = await _create_verified_user(client, created_emails, email)
    old_refresh_token = login_resp.cookies["refresh_token"]

    update_resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
    )
    assert update_resp.status_code == 200

    refresh_resp = await _post_with_refresh_cookie(client, "/auth/refresh/", old_refresh_token)
    assert refresh_resp.status_code == 401

    # The new password actually works.
    login_resp2 = await client.post(
        "/auth/login", json={"email": email, "password": "NewStrongPass456!"}
    )
    assert login_resp2.status_code == 200


@pytest.mark.asyncio
async def test_logout_after_self_password_change_still_succeeds_and_clears_cookies(client, created_emails):
    # Regression guard for the actual bug report: PUT /users/me revokes the
    # session's own refresh token (see test above), but never rotates or
    # clears its cookies, so the browser is still holding that now-revoked
    # refresh_token cookie. Clicking Logout right after a password-change
    # toast must not surface "invalid refresh token or already revoked" and
    # leave the user stuck looking logged in; it must still succeed and
    # actually clear both cookies, exactly like a logout with a live token.
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    update_resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
    )
    assert update_resp.status_code == 200
    assert any(cookie.name == "refresh_token" for cookie in client.cookies.jar)

    logout_resp = await client.post("/auth/logout")

    assert logout_resp.status_code == 200
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_logout_all_after_self_password_change_still_succeeds_and_clears_cookies(client, created_emails):
    # Same regression, logout-all variant: logout_all_handler previously
    # rejected an already-revoked refresh token outright (it couldn't even
    # recover the owning email to revoke the account's *other* sessions),
    # unlike plain logout's revoke-then-fail path.
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    update_resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
    )
    assert update_resp.status_code == 200
    assert any(cookie.name == "refresh_token" for cookie in client.cookies.jar)

    logout_all_resp = await client.post("/auth/logout/all")

    assert logout_all_resp.status_code == 200
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_logout_after_admin_password_change_for_another_user_still_succeeds_and_clears_cookies(
    client, created_emails
):
    # "Other users" variant of the bug report: an admin-driven password
    # change (PUT /users/{email}) revokes the TARGET account's sessions,
    # not the admin's own, so the target, still holding their own
    # now-revoked refresh_token cookie from before the admin acted, must
    # be able to log out cleanly too, not just the self-service path.
    target_email = _unique_email("target")
    target_login = await _create_verified_user(client, created_emails, target_email)
    target_refresh_token = target_login.cookies["refresh_token"]

    admin_email = _unique_email("admin")
    # Logs in as admin on the same shared client, replacing the cookie jar
    # this mirrors a real second browser/session, not the target's own tab.
    await _create_admin(client, created_emails, admin_email)

    admin_update_resp = await client.put(
        f"/users/{target_email}", json={"password": "NewStrongPass456!"}
    )
    assert admin_update_resp.status_code == 200

    # The target's own now-revoked cookie, explicitly presented: the jar
    # currently holds the admin's session, not the target's.
    logout_resp = await _post_with_refresh_cookie(client, "/auth/logout", target_refresh_token)

    assert logout_resp.status_code == 200
    # The response's Set-Cookie deletes "refresh_token" at path=/auth
    # regardless of whose value the jar currently holds under that same
    # (name, path) key, so this also proves the admin's own still-live
    # refresh_token cookie doesn't survive the target's logout call.
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_repeated_logout_calls_with_the_same_token_both_succeed(client, created_emails):
    # Simulates two tabs, or a client retrying a request it never saw the
    # response for: the same refresh_token value presented twice. The
    # second call's token is already revoked by the first and must still
    # succeed rather than error, exactly like the post-password-change case.
    email = _unique_email()
    login_resp = await _create_verified_user(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    first_logout = await _post_with_refresh_cookie(client, "/auth/logout", refresh_token)
    assert first_logout.status_code == 200

    second_logout = await _post_with_refresh_cookie(client, "/auth/logout", refresh_token)
    assert second_logout.status_code == 200


@pytest.mark.asyncio
async def test_logout_with_malformed_refresh_token_cookie_still_succeeds_and_clears_cookies(client, created_emails):
    # Not just "a real but revoked token": a cookie value that isn't even
    # a decodable JWT at all (corrupted, truncated, tampered) must be
    # handled the same lenient way, not treated as a different error class.
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    logout_resp = await _post_with_refresh_cookie(client, "/auth/logout", "not-a-real-jwt")

    assert logout_resp.status_code == 200
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_logout_all_with_malformed_refresh_token_cookie_still_succeeds_and_clears_cookies(
    client, created_emails
):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    logout_all_resp = await _post_with_refresh_cookie(client, "/auth/logout/all", "not-a-real-jwt")

    assert logout_all_resp.status_code == 200
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_self_password_change_requires_current_password(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    resp = await client.put("/users/me", json={"password": "NewStrongPass456!"})

    assert resp.status_code == 400
    assert "current password" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_self_password_change_rejects_wrong_current_password(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": "WrongPassword1"}
    )

    assert resp.status_code == 400
    assert "current password" in resp.json()["detail"].lower()

    # The old password must still work: the rejected change had no effect.
    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_self_password_change_rejects_same_password(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)

    resp = await client.put(
        "/users/me", json={"password": PASSWORD, "current_password": PASSWORD}
    )

    assert resp.status_code == 400
    assert "different from the current password" in resp.json()["detail"].lower()

    # No session revocation happened: the old password still works.
    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_password_change_rejects_same_password(client, created_emails):
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"password": PASSWORD})

    assert resp.status_code == 400
    assert "different from the current password" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_setting_a_first_password_on_an_oauth_only_account_does_not_require_current_password(
    client, created_emails
):
    # An OAuth-only account has hashed_password=None, so there is nothing yet
    # to confirm against, so the current-password requirement must not
    # block this, otherwise such an account could never add a password.
    email = _unique_email()
    await _create_verified_user(client, created_emails, email)
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        user.hashed_password = None
        session.add(user)
        await session.commit()

    resp = await client.put("/users/me", json={"password": "NewStrongPass456!"})

    assert resp.status_code == 200
    assert resp.json()["has_password"] is True


@pytest.mark.asyncio
async def test_admin_password_change_does_not_require_admins_current_password(client, created_emails):
    # PUT /users/{email} reuses UserUpdate, but the current-password check
    # only applies to the self-service route (update_my_profile); an admin
    # changing someone else's password authenticates via their own
    # users:update_any permission, not by proving the target's old password.
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"password": "AdminSetPass456!"})

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_self_profile_update_without_password_does_not_revoke_sessions(client, created_emails):
    # Only a password change should trigger revocation: an ordinary name
    # update must not log the user out of their other sessions.
    email = _unique_email()
    login_resp = await _create_verified_user(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    update_resp = await client.put("/users/me", json={"name": "New Name"})
    assert update_resp.status_code == 200

    refresh_resp = await _post_with_refresh_cookie(client, "/auth/refresh/", refresh_token)
    assert refresh_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_password_change_revokes_targets_existing_sessions(client, created_emails):
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    target_login_resp = await _create_verified_user(client, created_emails, target_email)
    target_refresh_token = target_login_resp.cookies["refresh_token"]

    await _create_admin(client, created_emails, admin_email)  # overwrites the client's cookie jar

    update_resp = await client.put(
        f"/users/{target_email}", json={"password": "NewStrongPass456!"}
    )
    assert update_resp.status_code == 200

    refresh_resp = await _post_with_refresh_cookie(client, "/auth/refresh/", target_refresh_token)
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_without_purge_permission_cannot_purge(client, created_emails):
    # users:purge is granted only by system_superuser: an admin holding
    # only user_administration (which includes users:delete_any) does not
    # have it; hard delete is a deliberately separate, more sensitive action.
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{target_email}/purge")
    assert resp.status_code == 403

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user is not None  # untouched: the purge was rejected


@pytest.mark.asyncio
async def test_system_user_can_purge_a_user(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_system_user(client, created_emails, system_email)

    resp = await client.delete(f"/users/{target_email}/purge")
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user is None  # row permanently gone


@pytest.mark.asyncio
async def test_admin_cannot_purge_system_user(client, created_emails):
    admin_email = _unique_email("admin")
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    await _create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{system_email}/purge")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_user_can_reactivate_a_soft_deleted_user(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_system_user(client, created_emails, system_email)

    delete_resp = await client.delete(f"/users/{target_email}")
    assert delete_resp.status_code == 200

    reactivate_resp = await client.patch(f"/users/{target_email}/reactivate")
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["is_active"] is True
    assert reactivate_resp.json()["deleted_at"] is None

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.is_active is True
        assert user.deleted_at is None

    # The reactivated account can log in again with its original password.
    login_resp = await client.post(
        "/auth/login", json={"email": target_email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reactivate_rejects_a_never_deleted_user(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_system_user(client, created_emails, system_email)

    resp = await client.patch(f"/users/{target_email}/reactivate")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_without_reactivate_permission_cannot_reactivate(client, created_emails):
    # users:reactivate is granted only by system_superuser, same tier as
    # users:purge, restoring access is more sensitive than day-to-day
    # user administration.
    admin_email = _unique_email("admin")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email)
    await _create_admin(client, created_emails, admin_email)

    delete_resp = await client.delete(f"/users/{target_email}")
    assert delete_resp.status_code == 200

    resp = await client.patch(f"/users/{target_email}/reactivate")
    assert resp.status_code == 403
