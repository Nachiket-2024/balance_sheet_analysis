# tests/backend/mystic_auth/integration/user/test_user_self_service_logout_after_password_change_integration.py
#
# End-to-end coverage for /auth/logout and /auth/logout/all when the
# session's refresh token was already revoked by a preceding PUT /users/me
# password change. A password change revokes the session's own refresh
# token but doesn't rotate or clear its cookies, so the very next Logout
# click presents an already-revoked token; these tests guard that path.
import pytest

from .user_test_accounts import (
    PASSWORD,
    create_verified_user,
    post_with_refresh_cookie,
    unique_email,
)


@pytest.mark.asyncio
async def test_logout_after_self_password_change_still_succeeds_and_clears_cookies(client, created_emails):
    # PUT /users/me revokes the refresh token but doesn't clear its cookie,
    # so the browser still holds the now-revoked cookie. Logout must not
    # error on that and leave the user looking logged in; it must succeed
    # and clear both cookies, same as logging out with a live token.
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
    # Same case, logout-all variant: it must recover the owning email and
    # revoke the account's other sessions too, not just reject the
    # already-revoked token outright.
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
async def test_logout_all_returns_503_when_account_version_bump_is_unconfirmed(client, created_emails, mocker):
    # Unlike an already-revoked token (nothing left to revoke, goal already
    # met), an unconfirmed account-version bump means logout-all's actual
    # purpose, revoking every session, genuinely didn't happen, so it must
    # not report success.
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.jwt_service.bump_account_version",
        new_callable=mocker.AsyncMock,
        return_value=False,
    )

    logout_all_resp = await client.post("/auth/logout/all")

    assert logout_all_resp.status_code == 503
    assert logout_all_resp.json()["code"] == "SESSION_REVOCATION_UNAVAILABLE"
    # Cookies are still cleared here regardless of other devices.
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_repeated_logout_calls_with_the_same_token_both_succeed(client, created_emails):
    # Simulates two tabs, or a retried request: same refresh token
    # presented twice. The second call's token is already revoked by the
    # first and must still succeed rather than error.
    email = unique_email()
    login_resp = await create_verified_user(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    first_logout = await post_with_refresh_cookie(client, "/auth/logout", refresh_token)
    assert first_logout.status_code == 200

    second_logout = await post_with_refresh_cookie(client, "/auth/logout", refresh_token)
    assert second_logout.status_code == 200


@pytest.mark.asyncio
async def test_logout_with_malformed_refresh_token_cookie_still_succeeds_and_clears_cookies(client, created_emails):
    # A cookie value that isn't even a decodable JWT (corrupted, truncated,
    # tampered) must be handled the same lenient way as a revoked token.
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
