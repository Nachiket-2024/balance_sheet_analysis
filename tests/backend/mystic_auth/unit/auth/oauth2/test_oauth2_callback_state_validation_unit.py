# CSRF state validation for handle_oauth2_callback: the state param must
# match its oauth_state cookie, be present, and be a fresh (non-replayed)
# single-use value before any token exchange with Google is attempted,
# plus the email_verified gate once a valid callback proceeds. See
# test_oauth2_login_handler_unit.py for state/PKCE generation and the
# cancellation/provider-error paths.
import pytest

from backend.mystic_auth.auth.oauth2.oauth2_login_handler import oauth2_login_handler
from backend.mystic_auth.core.settings import settings

FRONTEND_LOGIN_URL = f"{settings.FRONTEND_BASE_URL}/login"


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
    assert response.headers["location"] == f"{FRONTEND_LOGIN_URL}?error=OAUTH_STATE_INVALID"
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

    assert response.headers["location"] == f"{FRONTEND_LOGIN_URL}?error=OAUTH_STATE_INVALID"
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

    assert response.headers["location"] == f"{FRONTEND_LOGIN_URL}?error=OAUTH_STATE_INVALID"
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

    assert response.headers["location"] == f"{FRONTEND_LOGIN_URL}?error=OAUTH_STATE_INVALID"
    exchange_mock.assert_not_called()


@pytest.mark.asyncio
async def test_callback_proceeds_and_clears_state_cookie_on_valid_state(mocker, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
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
    assert "httponly" in cleared_cookie.lower()
    assert "secure" in cleared_cookie.lower()
    assert "samesite=lax" in cleared_cookie.lower()


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

    assert response.headers["location"] == f"{FRONTEND_LOGIN_URL}?error=OAUTH_EMAIL_NOT_VERIFIED"
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
        # No email_verified field at all: must not be assumed trustworthy
        return_value={"email": "user@example.com", "name": "Test User"},
    )
    login_or_create_mock = mocker.patch(
        "backend.mystic_auth.auth.oauth2.oauth2_login_handler.oauth2_service.login_or_create_user",
    )

    response = await oauth2_login_handler.handle_oauth2_callback(
        code="auth-code", state="matching-state", oauth_state_cookie="matching-state", db=None
    )

    assert response.headers["location"] == f"{FRONTEND_LOGIN_URL}?error=OAUTH_EMAIL_NOT_VERIFIED"
    login_or_create_mock.assert_not_called()
