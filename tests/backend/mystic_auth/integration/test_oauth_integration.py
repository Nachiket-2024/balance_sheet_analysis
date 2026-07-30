# tests/backend/mystic_auth/integration/test_oauth_integration.py
#
# OAuth2 account-linking / CSRF flows against the real ASGI app, real
# PostgreSQL, and real Redis (see conftest.py). The only mocked pieces are
# the two outbound calls to Google itself (token exchange, userinfo), an
# external third party CLAUDE.md permits mocking ("mock external
# dependencies only when required"). Everything else, including state
# generation and single-use consumption in Redis, account
# lookup/creation/linking in Postgres, and JWT issuance and cookie
# handling, is real.
import uuid
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.database.connection import database
from sqlalchemy import text

HANDLER_MODULE = "backend.mystic_auth.auth.oauth2.oauth2_login_handler"
PASSWORD = "StrongPass123!"


def _unique_email() -> str:
    return f"inttest-oauth-{uuid.uuid4().hex}@example.com"


def _mock_google(mocker, email: str, email_verified: bool = True):
    mocker.patch(
        f"{HANDLER_MODULE}.oauth2_service.exchange_code_for_tokens",
        new_callable=AsyncMock,
        return_value={"access_token": "fake-google-access-token"},
    )
    return mocker.patch(
        f"{HANDLER_MODULE}.oauth2_service.get_user_info",
        new_callable=AsyncMock,
        return_value={"email": email, "email_verified": email_verified, "name": "Google User"},
    )


async def _get_user_row(email: str):
    async with database.async_session() as session:
        result = await session.execute(text("SELECT is_verified, hashed_password FROM users WHERE email = :e"), {"e": email})
        return result.first()


@pytest.mark.asyncio
async def test_oauth2_new_user_is_created_verified_with_no_password(client, created_emails, mocker):
    email = _unique_email()
    _mock_google(mocker, email, email_verified=True)

    initiate_resp = await client.get("/auth/oauth2/login/google")
    state = initiate_resp.headers["location"].split("state=")[-1]

    callback_resp = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})
    created_emails.append(email)

    assert "dashboard" in callback_resp.headers["location"]
    assert "access_token" in callback_resp.cookies
    assert "refresh_token" in callback_resp.cookies

    row = await _get_user_row(email)
    assert row is not None
    assert row.is_verified is True
    assert row.hashed_password is None

    # The issued session actually works against a protected route.
    me_resp = await client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email


@pytest.mark.asyncio
async def test_oauth2_login_links_existing_unverified_password_account(client, created_emails, mocker):
    email = _unique_email()
    signup_resp = await client.post("/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD})
    assert signup_resp.status_code == 200
    created_emails.append(email)

    row_before = await _get_user_row(email)
    assert row_before.is_verified is False

    _mock_google(mocker, email, email_verified=True)
    initiate_resp = await client.get("/auth/oauth2/login/google")
    state = initiate_resp.headers["location"].split("state=")[-1]
    callback_resp = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})

    assert "dashboard" in callback_resp.headers["location"]

    # Existing password account is linked (verified), not duplicated, but
    # its password is cleared rather than preserved. See
    # test_oauth2_login_clears_password_on_pre_hijacked_unverified_account
    # for why: an *unverified* account's password was never proven to
    # belong to this email's real owner, so it must not survive the account
    # being claimed by whoever Google just verified as the owner.
    row_after = await _get_user_row(email)
    assert row_after.is_verified is True
    assert row_after.hashed_password is None

    async with database.async_session() as session:
        count = await session.execute(text("SELECT COUNT(*) FROM users WHERE email = :e"), {"e": email})
        assert count.scalar() == 1


@pytest.mark.asyncio
async def test_oauth2_login_clears_password_on_pre_hijacked_unverified_account(client, created_emails, mocker):
    # Pre-hijacking scenario end-to-end: an "attacker" signs up using the
    # victim's email with a password of their own choosing and never
    # verifies it. The real victim later signs in with Google (which
    # email_verified=True proves they own that address). The attacker's
    # password must stop working the instant the account is claimed,
    # otherwise the attacker could log in as the victim indefinitely.
    email = _unique_email()
    attacker_password = "AttackerChosenPass123!"
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Attacker-Controlled Name", "email": email, "password": attacker_password}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    row_before = await _get_user_row(email)
    assert row_before.is_verified is False
    assert row_before.hashed_password is not None

    _mock_google(mocker, email, email_verified=True)
    initiate_resp = await client.get("/auth/oauth2/login/google")
    state = initiate_resp.headers["location"].split("state=")[-1]
    callback_resp = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})
    assert "dashboard" in callback_resp.headers["location"]

    # The attacker's original password no longer authenticates this account.
    attacker_login_resp = await client.post("/auth/login", json={"email": email, "password": attacker_password})
    assert attacker_login_resp.status_code == 401

    row_after = await _get_user_row(email)
    assert row_after.is_verified is True
    assert row_after.hashed_password is None


@pytest.mark.asyncio
async def test_oauth2_login_does_not_touch_password_of_already_verified_account(client, created_emails, mocker):
    # The legitimate case CLAUDE.md requires: a password user who already
    # verified their email can add Google as an additional login method
    # without losing their existing password.
    email = _unique_email()
    signup_resp = await client.post("/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD})
    assert signup_resp.status_code == 200
    created_emails.append(email)

    from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service
    from backend.mystic_auth.redis.client import redis_client

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    _mock_google(mocker, email, email_verified=True)
    initiate_resp = await client.get("/auth/oauth2/login/google")
    state = initiate_resp.headers["location"].split("state=")[-1]
    callback_resp = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})
    assert "dashboard" in callback_resp.headers["location"]

    # Password login still works: Google was added as a second method, not
    # a replacement.
    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    row = await _get_user_row(email)
    assert row.hashed_password is not None


@pytest.mark.asyncio
async def test_oauth2_rejects_unverified_google_email(client, created_emails, mocker):
    email = _unique_email()
    _mock_google(mocker, email, email_verified=False)

    initiate_resp = await client.get("/auth/oauth2/login/google")
    state = initiate_resp.headers["location"].split("state=")[-1]

    callback_resp = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})

    assert "login" in callback_resp.headers["location"]
    assert "access_token" not in callback_resp.cookies

    row = await _get_user_row(email)
    assert row is None


@pytest.mark.asyncio
async def test_oauth2_callback_rejects_state_cookie_mismatch(client, created_emails, mocker):
    email = _unique_email()
    exchange_mock = _mock_google(mocker, email, email_verified=True)

    await client.get("/auth/oauth2/login/google")  # sets a real oauth_state cookie

    # Query-param state doesn't match whatever the cookie actually holds.
    callback_resp = await client.get(
        "/auth/oauth2/callback/google", params={"code": "fake-code", "state": "attacker-supplied-state"}
    )

    assert "login" in callback_resp.headers["location"]
    assert "access_token" not in callback_resp.cookies
    # Rejected before ever reaching Google: proves the CSRF check short-circuits.
    exchange_mock.assert_not_called()


@pytest.mark.asyncio
async def test_oauth2_state_token_is_single_use(client, created_emails, mocker):
    email = _unique_email()
    _mock_google(mocker, email, email_verified=True)

    initiate_resp = await client.get("/auth/oauth2/login/google")
    state = initiate_resp.headers["location"].split("state=")[-1]

    first = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})
    created_emails.append(email)
    assert "dashboard" in first.headers["location"]

    # Cookie is cleared by a successful callback, so mirror it back manually
    # to isolate what's being tested here: whether the *state* itself (not
    # the cookie) can be replayed.
    client.cookies.set("oauth_state", state)
    second = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})

    assert "login" in second.headers["location"]


@pytest.mark.asyncio
async def test_oauth2_pkce_mismatch_rejected_end_to_end_no_user_created(client, created_emails, mocker):
    # Simulates Google actually enforcing PKCE: a code_verifier that doesn't
    # match the code_challenge sent at authorization time gets the token
    # exchange rejected (400 invalid_grant), which exchange_code_for_tokens
    # surfaces as None (see the unit-level fail-closed test). This is the
    # real behavioral proof of the PKCE security property: a stolen
    # authorization code alone must never be enough to complete login.
    email = _unique_email()
    mocker.patch(
        f"{HANDLER_MODULE}.oauth2_service.exchange_code_for_tokens",
        new_callable=AsyncMock,
        return_value=None,
    )
    get_user_info_mock = mocker.patch(
        f"{HANDLER_MODULE}.oauth2_service.get_user_info", new_callable=AsyncMock
    )

    initiate_resp = await client.get("/auth/oauth2/login/google")
    state = initiate_resp.headers["location"].split("state=")[-1]

    callback_resp = await client.get("/auth/oauth2/callback/google", params={"code": "fake-code", "state": state})
    created_emails.append(email)

    assert "login" in callback_resp.headers["location"]
    assert "access_token" not in callback_resp.cookies
    # A rejected token exchange must never proceed to fetching user info or
    # creating/linking an account.
    get_user_info_mock.assert_not_called()
    row = await _get_user_row(email)
    assert row is None


@pytest.mark.asyncio
async def test_oauth2_cancelled_consent_redirects_cleanly_instead_of_422(client):
    # Regression guard: code/state used to be required route params with no
    # default, so Google's real cancellation redirect (?error=access_denied,
    # no code at all) previously hit FastAPI's own 422 validation response
    # instead of a clean redirect to the frontend login page.
    await client.get("/auth/oauth2/login/google")  # sets a real oauth_state cookie

    callback_resp = await client.get(
        "/auth/oauth2/callback/google", params={"error": "access_denied", "state": "whatever"}
    )

    assert callback_resp.status_code in (302, 307)
    assert "login" in callback_resp.headers["location"]
