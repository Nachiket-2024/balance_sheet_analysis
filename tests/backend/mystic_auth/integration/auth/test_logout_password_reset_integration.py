# tests/backend/mystic_auth/integration/test_logout_password_reset_integration.py
#
# End-to-end logout/logout-all and password-reset coverage against the real
# ASGI app, real PostgreSQL, and real Redis (see conftest.py). Split out of
# what used to be one 799-line test_auth_api_integration.py: both flows
# share the same "revoke sessions/tokens account-wide" shape, unlike
# refresh rotation or login, which is why they're grouped together here.
import asyncio

import pytest
from backend.mystic_auth.auth.password_logic.password_service import (
    password_service,
)
from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.redis.client import redis_client

from .auth_test_accounts import (
    PASSWORD,
    get_me_with_access_token,
    refresh_with_cookie,
    signup_verify_login,
    unique_email,
)

# ---------------------------- logout / logout-all ----------------------------

@pytest.mark.asyncio
async def test_logout_actually_clears_the_scoped_refresh_token_cookie(client, created_emails):
    # Regression guard: logout's delete_cookie call must use the same
    # path="/auth" the cookie was set with, or the browser (real cookie jar
    # here) never actually removes it, it just leaves the real one behind
    # and layers an ignored, differently-scoped tombstone next to it.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    assert any(cookie.name == "refresh_token" for cookie in client.cookies.jar)

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    reuse_resp = await refresh_with_cookie(client, refresh_token)
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_revokes_every_device(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    device_a_refresh = login_resp.cookies["refresh_token"]

    second_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    device_b_refresh = second_login.cookies["refresh_token"]

    logout_all_resp = await client.post("/auth/logout/all")
    assert logout_all_resp.status_code == 200

    a_resp = await refresh_with_cookie(client, device_a_refresh)
    b_resp = await refresh_with_cookie(client, device_b_refresh)
    assert a_resp.status_code == 401
    assert b_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_immediately_invalidates_already_issued_access_tokens(client, created_emails):
    """Regression guard: logout-all used to only revoke each device's
    refresh token, leaving its still-valid (short-lived but not instant)
    access token fully usable for up to ACCESS_TOKEN_EXPIRE_MINUTES - a
    device that had already been logged in stayed logged in until it next
    tried to refresh, not "immediately" as documented. Confirms
    revoke_all_tokens_for_user's account_ver bump actually kills a
    still-unexpired access token from a different device right away, not
    just on its next refresh."""
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    device_a_access = login_resp.cookies["access_token"]

    second_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    device_b_access = second_login.cookies["access_token"]

    # Sanity check: both access tokens work before logout-all.
    assert (await get_me_with_access_token(client, device_a_access)).status_code == 200
    assert (await get_me_with_access_token(client, device_b_access)).status_code == 200

    logout_all_resp = await client.post("/auth/logout/all")
    assert logout_all_resp.status_code == 200

    a_me_resp = await get_me_with_access_token(client, device_a_access)
    b_me_resp = await get_me_with_access_token(client, device_b_access)
    assert a_me_resp.status_code == 401
    assert b_me_resp.status_code == 401

    # A token minted *after* the revoke (e.g. logging back in) must still
    # work. Validity is an integer version comparison (account_ver), not
    # time-based, so this needs no delay to avoid same-second ambiguity -
    # login_resp above already embeds the bumped account_ver.
    fresh_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert fresh_login.status_code == 200
    fresh_access = fresh_login.cookies["access_token"]
    assert (await get_me_with_access_token(client, fresh_access)).status_code == 200


# ---------------------------- password reset ----------------------------

async def _request_password_reset(client, email: str) -> str:
    """Mirrors password_reset_service.send_reset_email's Redis single-use
    registration so the test can drive password-reset/confirm without
    depending on the Taskiq email worker being up to deliver the link."""
    resp = await client.post("/auth/password-reset/request", json={"email": email})
    assert resp.status_code == 200

    token = await password_service.create_reset_token(email)
    await redis_client.set(f"password_reset:{token}", "1", ex=settings.RESET_TOKEN_EXPIRE_MINUTES * 60)
    return token


@pytest.mark.asyncio
async def test_password_reset_revokes_existing_sessions(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    old_refresh = login_resp.cookies["refresh_token"]

    new_password = "EvenStrongerPass456!"
    reset_token = await _request_password_reset(client, email)

    confirm_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": reset_token, "new_password": new_password}
    )
    assert confirm_resp.status_code == 200

    # The gap finding #2 fixed: a stolen refresh token from before the reset
    # must no longer work afterwards.
    reuse_resp = await refresh_with_cookie(client, old_refresh)
    assert reuse_resp.status_code == 401

    # New credentials work; old ones don't.
    old_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert old_login.status_code == 401
    new_login = await client.post("/auth/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_token_is_single_use(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)

    reset_token = await _request_password_reset(client, email)

    first = await client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "FirstNewPass123!"},
    )
    second = await client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "SecondNewPass456!"},
    )

    assert first.status_code == 200
    assert second.status_code != 200


@pytest.mark.asyncio
async def test_password_reset_survives_retry_after_weak_password(client, created_emails):
    # Regression guard for the TOCTOU fix: a recoverable validation failure
    # (weak password) must restore the token rather than permanently
    # consuming it, otherwise a user who mistypes a weak password on their
    # first attempt would be locked out of their own valid reset link.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    reset_token = await _request_password_reset(client, email)

    weak_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": reset_token, "new_password": "weak"}
    )
    assert weak_resp.status_code != 200

    retry_resp = await client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "StrongRetryPass789!"},
    )
    assert retry_resp.status_code == 200

    login_resp = await client.post(
        "/auth/login", json={"email": email, "password": "StrongRetryPass789!"}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_concurrent_requests_only_one_succeeds(client, created_emails):
    # The core TOCTOU race (real Redis, real Postgres): two requests firing
    # concurrently with the same valid token and *different* new passwords
    # must not both succeed: GETDEL's atomicity means only one can ever
    # win the single-use check, regardless of how the DB writes interleave.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    reset_token = await _request_password_reset(client, email)

    responses = await asyncio.gather(
        client.post(
            "/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "ConcurrentPassA1!"},
        ),
        client.post(
            "/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "ConcurrentPassB2!"},
        ),
    )

    statuses = sorted(resp.status_code for resp in responses)
    # Exactly one of the two concurrent requests may succeed; the other
    # loses the atomic GETDEL and gets password_reset_confirm_handler's
    # standard "Invalid token or password" failure response.
    assert statuses == [200, 400]

    # Confirm exactly one of the two candidate passwords actually works.
    login_a = await client.post("/auth/login", json={"email": email, "password": "ConcurrentPassA1!"})
    login_b = await client.post("/auth/login", json={"email": email, "password": "ConcurrentPassB2!"})
    assert sorted([login_a.status_code, login_b.status_code]) == [200, 401]
