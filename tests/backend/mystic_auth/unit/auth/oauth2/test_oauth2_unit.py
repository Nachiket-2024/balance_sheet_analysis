# tests/backend/mystic_auth/unit/test_oauth2_unit.py
import base64
import hashlib
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.oauth2.oauth2_login_handler import oauth2_login_handler
from backend.mystic_auth.auth.oauth2.oauth2_service import (
    OAUTH2_STATE_TTL_SECONDS,
    oauth2_service,
)


def _cookie_headers(response):
    """Extract every raw Set-Cookie header value from a Starlette response."""
    return [
        value.decode() for key, value in response.raw_headers if key == b"set-cookie"
    ]


def _cookie_value(response, name):
    for header in _cookie_headers(response):
        if header.startswith(f"{name}="):
            return header.split(";", 1)[0].split("=", 1)[1]
    return None


# ---------------------------- generate_and_store_state / consume_state ----------------------------

@pytest.mark.asyncio
async def test_generate_and_store_state_persists_verifier_keyed_by_state(mocker):
    set_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_service.redis_client.set",
        new_callable=AsyncMock,
    )

    state, code_challenge = await oauth2_login_handler.oauth2_service.generate_and_store_state()

    assert isinstance(state, str) and len(state) > 20
    assert isinstance(code_challenge, str) and len(code_challenge) > 20
    # code_challenge must never be the raw verifier itself (must be a SHA256
    # digest of it) : anyone who could see the challenge would otherwise be
    # able to complete the PKCE exchange without ever having the verifier.
    set_mock.assert_awaited_once()
    args, kwargs = set_mock.call_args
    assert args[0] == f"oauth_state:{state}"
    stored_code_verifier = args[1]
    assert stored_code_verifier != code_challenge
    assert kwargs == {"ex": OAUTH2_STATE_TTL_SECONDS}


@pytest.mark.asyncio
async def test_consume_state_rejects_empty_state():
    assert await oauth2_login_handler.oauth2_service.consume_state("") is None
    assert await oauth2_login_handler.oauth2_service.consume_state(None) is None


@pytest.mark.asyncio
async def test_consume_state_returns_verifier_once_then_rejected_on_replay(mocker):
    getdel_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_service.redis_client.getdel",
        new_callable=AsyncMock,
        side_effect=["stored-code-verifier", None],
    )

    assert await oauth2_login_handler.oauth2_service.consume_state("abc") == "stored-code-verifier"
    assert await oauth2_login_handler.oauth2_service.consume_state("abc") is None
    assert getdel_mock.await_count == 2


@pytest.mark.asyncio
async def test_generate_and_store_state_pkce_challenge_is_correct_sha256_derivation(mocker):
    # Pins the exact RFC 7636 S256 transform: code_challenge must be the
    # base64url(no padding) of SHA256(code_verifier) : anything looser (e.g.
    # storing the verifier itself as the challenge) would let a network
    # observer of the authorization request alone complete the token
    # exchange without ever needing the verifier, defeating PKCE entirely.
    set_mock = mocker.patch("backend.mystic_auth.auth.oauth2.oauth2_service.redis_client.set", new_callable=AsyncMock)

    _, code_challenge = await oauth2_service.generate_and_store_state()

    stored_verifier = set_mock.call_args.args[1]
    expected_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(stored_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    assert code_challenge == expected_challenge


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_sends_pkce_code_verifier_to_google(mocker):
    post_mock = AsyncMock()
    post_mock.return_value.raise_for_status = lambda: None
    post_mock.return_value.json = lambda: {"access_token": "google-access-token"}

    mock_client = mocker.patch("backend.mystic_auth.auth.oauth2.oauth2_service.httpx.AsyncClient")
    mock_client.return_value.__aenter__.return_value.post = post_mock

    await oauth2_service.exchange_code_for_tokens(
        code="auth-code",
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://example.com/callback",
        code_verifier="the-real-verifier",
    )

    _, kwargs = post_mock.call_args
    assert kwargs["data"]["code_verifier"] == "the-real-verifier"


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_fails_closed_on_pkce_mismatch(mocker):
    # The actual PKCE security property: if code_verifier doesn't match the
    # code_challenge sent at authorization time, Google rejects the token
    # exchange (400 invalid_grant) : raise_for_status turns that into an
    # exception, which this method must fail closed on (return None), never
    # returning any partial/fabricated token data.
    import httpx

    post_mock = AsyncMock()
    post_mock.return_value.raise_for_status = mocker.Mock(
        side_effect=httpx.HTTPStatusError("400 Bad Request", request=mocker.Mock(), response=mocker.Mock())
    )

    mock_client = mocker.patch("backend.mystic_auth.auth.oauth2.oauth2_service.httpx.AsyncClient")
    mock_client.return_value.__aenter__.return_value.post = post_mock

    result = await oauth2_service.exchange_code_for_tokens(
        code="auth-code",
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://example.com/callback",
        code_verifier="wrong-verifier",
    )

    assert result is None


# ---------------------------- handle_oauth2_login_initiate ----------------------------

@pytest.mark.asyncio
async def test_oauth2_login_initiate_embeds_state_and_pkce_challenge_in_url_and_cookie(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.generate_and_store_state",
        return_value=("test-state-value", "test-code-challenge"),
    )

    response = await oauth2_login_handler.handle_oauth2_login_initiate()

    assert "state=test-state-value" in response.headers["location"]
    assert "code_challenge=test-code-challenge" in response.headers["location"]
    assert "code_challenge_method=S256" in response.headers["location"]
    assert _cookie_value(response, "oauth_state") == "test-state-value"
    cookie_header = next(h for h in _cookie_headers(response) if h.startswith("oauth_state="))
    assert "samesite=lax" in cookie_header.lower()
    assert "httponly" in cookie_header.lower()
    assert "secure" in cookie_header.lower()


# ---------------------------- handle_oauth2_callback: cancellation / provider errors ----------------------------
# Regression guard: code/state used to be required route params with no
# default, so a cancelled Google consent screen (which redirects back with
# only ?error=access_denied and no code) previously hit FastAPI's own 422
# validation error before ever reaching this handler, instead of a clean
# redirect to the frontend login page.

@pytest.mark.asyncio
async def test_callback_redirects_cleanly_on_provider_error_without_touching_state(mocker):
    consume_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
    )
    exchange_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code=None, state="some-state", oauth_state_cookie="some-state", error="access_denied", db=None
    )

    assert response.headers["location"].endswith("/login")
    consume_mock.assert_not_called()
    exchange_mock.assert_not_called()


@pytest.mark.asyncio
async def test_callback_redirects_cleanly_when_code_is_missing_without_error(mocker):
    consume_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code=None, state="some-state", oauth_state_cookie="some-state", error=None, db=None
    )

    assert response.headers["location"].endswith("/login")
    consume_mock.assert_not_called()


# ---------------------------- handle_oauth2_callback: CSRF state validation ----------------------------

@pytest.mark.asyncio
async def test_callback_rejects_missing_state(mocker):
    consume_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
    )
    exchange_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="", oauth_state_cookie="cookie-state", db=None
    )

    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/login")
    consume_mock.assert_not_called()
    exchange_mock.assert_not_called()


@pytest.mark.asyncio
async def test_callback_rejects_missing_cookie(mocker):
    exchange_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="query-state", oauth_state_cookie=None, db=None
    )

    assert response.headers["location"].endswith("/login")
    exchange_mock.assert_not_called()


@pytest.mark.asyncio
async def test_callback_rejects_state_cookie_mismatch(mocker):
    consume_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
    )
    exchange_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="query-state", oauth_state_cookie="different-state", db=None
    )

    assert response.headers["location"].endswith("/login")
    consume_mock.assert_not_called()
    exchange_mock.assert_not_called()


@pytest.mark.asyncio
async def test_callback_rejects_expired_or_replayed_state(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
        return_value=None,
    )
    exchange_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="matching-state", oauth_state_cookie="matching-state", db=None
    )

    assert response.headers["location"].endswith("/login")
    exchange_mock.assert_not_called()


@pytest.mark.asyncio
async def test_callback_proceeds_and_clears_state_cookie_on_valid_state(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
        return_value="stored-code-verifier",
    )
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
        return_value={"access_token": "google-access-token"},
    )
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.get_user_info",
        return_value={"email": "user@example.com", "name": "Test User", "email_verified": True},
    )
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.login_or_create_user",
        return_value={"access_token": "app-access-token", "refresh_token": "app-refresh-token"},
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="matching-state", oauth_state_cookie="matching-state", db=None
    )

    assert response.headers["location"].endswith("/dashboard")
    assert _cookie_value(response, "access_token") == "app-access-token"
    # oauth_state cookie must be cleared once its single-use state token is consumed
    cleared_cookie = next(h for h in _cookie_headers(response) if h.startswith("oauth_state="))
    assert cleared_cookie.startswith(("oauth_state=\"\"", "oauth_state=;"))


@pytest.mark.asyncio
async def test_callback_rejects_unverified_google_email(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
        return_value="stored-code-verifier",
    )
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
        return_value={"access_token": "google-access-token"},
    )
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.get_user_info",
        return_value={"email": "attacker@example.com", "name": "Unverified", "email_verified": False},
    )
    login_or_create_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.login_or_create_user",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="matching-state", oauth_state_cookie="matching-state", db=None
    )

    assert response.headers["location"].endswith("/login")
    # An unverified email must never reach account creation/linking
    login_or_create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_callback_rejects_missing_email_verified_field(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.consume_state",
        return_value="stored-code-verifier",
    )
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.exchange_code_for_tokens",
        return_value={"access_token": "google-access-token"},
    )
    mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.get_user_info",
        # No email_verified field at all : must not be assumed trustworthy
        return_value={"email": "user@example.com", "name": "Test User"},
    )
    login_or_create_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.login_or_create_user",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="matching-state", oauth_state_cookie="matching-state", db=None
    )

    assert response.headers["location"].endswith("/login")
    login_or_create_mock.assert_not_called()
