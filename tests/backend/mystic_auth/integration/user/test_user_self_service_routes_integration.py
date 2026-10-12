# tests/backend/mystic_auth/integration/user/test_user_self_service_routes_integration.py
#
# End-to-end coverage for GET/PUT /users/me (user_self_service_routes.py).
#
# Self-service account deletion (DELETE /users/me and its OAuth-only
# confirm-delete flow) lives in
# test_user_self_service_account_deletion_integration.py; the
# logout/logout-all tests for the post-password-change case live in
# test_user_self_service_logout_after_password_change_integration.py.
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud

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
    # role is nullable so a roleless account can still authenticate and be
    # authorized purely via its assigned policies, with no role fallback.
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
    # A password change revokes existing sessions, on the theory that the
    # change may be happening because the account is compromised.
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
async def test_self_password_change_reports_sessions_revoked_true_on_success(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    update_resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
    )

    assert update_resp.status_code == 200
    assert update_resp.json()["sessions_revoked"] is True


@pytest.mark.asyncio
async def test_self_password_change_succeeds_but_flags_unrevoked_sessions_when_valkey_is_unreachable(
    client, created_emails, mocker
):
    # The password write (Postgres) must still succeed even if the
    # account-version bump (Valkey) can't be confirmed, but the response
    # must say so rather than pretending every session was revoked.
    email = unique_email()
    login_resp = await create_verified_user(client, created_emails, email)
    old_refresh_token = login_resp.cookies["refresh_token"]

    # bump_account_version is a bound-method reference captured at import
    # time, so patching the class wouldn't reach it; patch the instance
    # attribute directly instead.
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.jwt_service.bump_account_version",
        new_callable=mocker.AsyncMock,
        return_value=False,
    )

    update_resp = await client.put(
        "/users/me", json={"password": "NewStrongPass456!", "current_password": PASSWORD}
    )

    assert update_resp.status_code == 200
    assert update_resp.json()["sessions_revoked"] is False

    # The password itself really did change.
    login_resp2 = await client.post(
        "/auth/login", json={"email": email, "password": "NewStrongPass456!"}
    )
    assert login_resp2.status_code == 200

    # The account-version bump never happened, so the old refresh token is
    # still valid: the gap the response field is warning about.
    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", old_refresh_token)
    assert refresh_resp.status_code == 200


@pytest.mark.asyncio
async def test_self_password_change_does_not_log_out_the_device_that_made_it(client, created_emails):
    # A password change must revoke every other session, but not the
    # device it was made from: that device already proved itself by
    # supplying the current password.
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
    # An OAuth-only account has hashed_password=None, so there's nothing to
    # confirm against; the current-password requirement must not block
    # this, or such an account could never add a password.
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
