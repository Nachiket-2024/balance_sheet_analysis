# tests/backend/mystic_auth/integration/test_user_self_service_routes_integration.py
#
# End-to-end coverage for GET/PUT /users/me (user_self_service_routes.py)
# against the real ASGI app, real PostgreSQL, and real Redis (see
# conftest.py). Split out of what used to be one 963-line
# test_user_routes_integration.py, mirroring the same self-service vs.
# management split already done on the source side. Also covers the
# logout/logout-all robustness tests authored alongside the self-service
# password-change tests (they exercise /auth/logout directly, not
# /users/me, but were part of the same bug-fix investigation and stay
# grouped with it rather than being scattered into an unrelated auth file).
import pytest
from backend.app.main import app
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user_crud.user_crud_collector import user_crud
from httpx import ASGITransport, AsyncClient

from .user_test_accounts import (
    PASSWORD,
    create_roleless_user,
    create_verified_user,
    post_with_refresh_cookie,
    unique_email,
)


@pytest.mark.asyncio
async def test_regular_user_can_update_own_profile(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    resp = await client.put("/users/me", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_roleless_user_can_authenticate_and_use_self_service(client, created_emails):
    # Per the role-as-metadata invariant: "The system must support ... users
    # without roles". role is nullable precisely so this is possible (see
    # user_model.py): a roleless account must still authenticate (real
    # login, real JWT, real GET /auth/me) and be authorized purely via its
    # assigned policies, with no fallback to any role-based behavior anywhere.
    email = unique_email("roleless")
    await create_roleless_user(created_emails, email, [SELF_SERVICE_POLICY_NAME])

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
async def test_self_password_change_revokes_existing_sessions(client, created_emails):
    # Regression guard: changing a password via PUT /users/me previously left
    # every existing session alive, unlike password_reset_service.py's
    # equivalent flow (which explicitly revokes on the theory that a
    # password change may be happening because the account is compromised).
    email = unique_email()
    login_resp = await create_verified_user(client, created_emails, email)
    old_refresh_token = login_resp.cookies["refresh_token"]

    update_resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
    )
    assert update_resp.status_code == 200

    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", old_refresh_token)
    assert refresh_resp.status_code == 401

    # The new password actually works.
    login_resp2 = await client.post(
        "/auth/login", json={"email": email, "password": "NewStrongPass456!"}
    )
    assert login_resp2.status_code == 200


@pytest.mark.asyncio
async def test_self_password_change_does_not_log_out_the_device_that_made_it(client, created_emails):
    # A password change must revoke every OTHER session (see test above),
    # but not the device the change was actually made from: that device
    # just supplied the current password, so it already proved it isn't an
    # attacker riding along on a stolen session.
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    # A second, independent "device": its own login, its own cookie jar.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver", follow_redirects=False) as other_device:
        other_login = await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert other_login.status_code == 200
        other_refresh_token = other_login.cookies["refresh_token"]

        update_resp = await client.put(
            "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
        )
        assert update_resp.status_code == 200

        # The device that made the change is still authenticated, with no
        # re-login required.
        me_resp = await client.get("/users/me")
        assert me_resp.status_code == 200

        # The OTHER device's session was revoked by the same change.
        other_refresh_resp = await post_with_refresh_cookie(other_device, "/auth/refresh/", other_refresh_token)
        assert other_refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_after_self_password_change_still_succeeds_and_clears_cookies(client, created_emails):
    # Regression guard for the actual bug report: PUT /users/me revokes the
    # session's own refresh token (see test above), but never rotates or
    # clears its cookies, so the browser is still holding that now-revoked
    # refresh_token cookie. Clicking Logout right after a password-change
    # toast must not surface "invalid refresh token or already revoked" and
    # leave the user stuck looking logged in; it must still succeed and
    # actually clear both cookies, exactly like a logout with a live token.
    email = unique_email()
    await create_verified_user(client, created_emails, email)

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
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    update_resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
    )
    assert update_resp.status_code == 200
    assert any(cookie.name == "refresh_token" for cookie in client.cookies.jar)

    logout_all_resp = await client.post("/auth/logout/all")

    assert logout_all_resp.status_code == 200
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_repeated_logout_calls_with_the_same_token_both_succeed(client, created_emails):
    # Simulates two tabs, or a client retrying a request it never saw the
    # response for: the same refresh_token value presented twice. The
    # second call's token is already revoked by the first and must still
    # succeed rather than error, exactly like the post-password-change case.
    email = unique_email()
    login_resp = await create_verified_user(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    first_logout = await post_with_refresh_cookie(client, "/auth/logout", refresh_token)
    assert first_logout.status_code == 200

    second_logout = await post_with_refresh_cookie(client, "/auth/logout", refresh_token)
    assert second_logout.status_code == 200


@pytest.mark.asyncio
async def test_logout_with_malformed_refresh_token_cookie_still_succeeds_and_clears_cookies(client, created_emails):
    # Not just "a real but revoked token": a cookie value that isn't even
    # a decodable JWT at all (corrupted, truncated, tampered) must be
    # handled the same lenient way, not treated as a different error class.
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    logout_resp = await post_with_refresh_cookie(client, "/auth/logout", "not-a-real-jwt")

    assert logout_resp.status_code == 200
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_logout_all_with_malformed_refresh_token_cookie_still_succeeds_and_clears_cookies(
    client, created_emails
):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    logout_all_resp = await post_with_refresh_cookie(client, "/auth/logout/all", "not-a-real-jwt")

    assert logout_all_resp.status_code == 200
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_self_password_change_requires_current_password(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    resp = await client.put("/users/me", json={"password": "NewStrongPass456!"})

    assert resp.status_code == 400
    assert "current password" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_self_password_change_rejects_wrong_current_password(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

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
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    resp = await client.put(
        "/users/me", json={"password": PASSWORD, "current_password": PASSWORD}
    )

    assert resp.status_code == 400
    assert "different from the current password" in resp.json()["detail"].lower()

    # No session revocation happened: the old password still works.
    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_setting_a_first_password_on_an_oauth_only_account_does_not_require_current_password(
    client, created_emails
):
    # An OAuth-only account has hashed_password=None, so there is nothing yet
    # to confirm against, so the current-password requirement must not
    # block this, otherwise such an account could never add a password.
    email = unique_email()
    await create_verified_user(client, created_emails, email)
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        user.hashed_password = None
        session.add(user)
        await session.commit()

    resp = await client.put("/users/me", json={"password": "NewStrongPass456!"})

    assert resp.status_code == 200
    assert resp.json()["has_password"] is True


@pytest.mark.asyncio
async def test_self_profile_update_without_password_does_not_revoke_sessions(client, created_emails):
    # Only a password change should trigger revocation: an ordinary name
    # update must not log the user out of their other sessions.
    email = unique_email()
    login_resp = await create_verified_user(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    update_resp = await client.put("/users/me", json={"name": "New Name"})
    assert update_resp.status_code == 200

    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", refresh_token)
    assert refresh_resp.status_code == 200
