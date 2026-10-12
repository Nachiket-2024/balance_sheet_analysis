import json
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.logout.logout_handler import logout_handler

MODULE = "backend.mystic_auth.auth.logout.logout_handler"


def _set_cookie_headers(response) -> list[str]:
    return [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]


def _mock_decode(mocker, email="user@example.com", jti="jti-1"):
    payload = {"email": email, "type": "refresh", "jti": jti} if email else None
    return mocker.patch(f"{MODULE}.jwt_service.decode_payload", new_callable=AsyncMock, return_value=payload)


@pytest.mark.asyncio
async def test_logout_without_refresh_token_returns_400(mocker):
    revoke_mock = mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout(None)

    assert response.status_code == 400
    revoke_mock.assert_not_called()


@pytest.mark.asyncio
async def test_logout_with_already_revoked_token_still_succeeds_and_clears_cookies(mocker):
    # Regression guard: this is what a stale/dead refresh-token cookie
    # looks like right after a password change (which revokes every
    # session for the account). decode_payload still resolves it (it
    # skips the revocation check verify_token would apply), so this must
    # not be treated as an error: the caller's goal (no valid session left
    # in this browser) is already true, so logout should still report
    # success and clear both cookies.
    _mock_decode(mocker)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout("already-revoked-token")

    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_response_carries_session_revoked_true_on_success(mocker):
    _mock_decode(mocker)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout("valid-token")

    assert json.loads(response.body)["session_revoked"] is True


@pytest.mark.asyncio
async def test_logout_still_reports_200_and_clears_cookies_when_revocation_is_unconfirmed(mocker):
    """Unlike logout-all/Manage Sessions, plain logout keeps its "always
    succeed, clear cookies regardless" contract even when Valkey couldn't
    confirm the chain-version bump. The gap must still be visible in the
    response body, though, not silently indistinguishable from a real
    revoke."""
    _mock_decode(mocker)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=False)

    response = await logout_handler.handle_logout("valid-token")

    assert response.status_code == 200
    assert json.loads(response.body)["session_revoked"] is False
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_success_clears_both_cookies(mocker):
    _mock_decode(mocker)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout("valid-token")

    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_clears_refresh_token_cookie_with_matching_auth_path(mocker):
    # Regression guard: refresh_token is set with path="/auth"
    # (token_cookie_handler.py). A delete_cookie call without the same
    # path creates a different cookie the browser expires immediately,
    # leaving the real, still-valid "/auth"-scoped cookie behind.
    _mock_decode(mocker)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout("valid-token")

    headers = _set_cookie_headers(response)
    refresh_header = next(h for h in headers if h.startswith("refresh_token="))
    assert "Path=/auth" in refresh_header


@pytest.mark.asyncio
async def test_logout_undecodable_token_still_clears_refresh_cookie_with_matching_auth_path(mocker):
    # Same regression guard as above, for a token that fails to decode
    # entirely: a fix that clears cookies but forgets the matching
    # path=/auth would silently reintroduce the original bug here.
    _mock_decode(mocker, email=None)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout("garbage-token")

    headers = _set_cookie_headers(response)
    refresh_header = next(h for h in headers if h.startswith("refresh_token="))
    assert "Path=/auth" in refresh_header


@pytest.mark.asyncio
async def test_logout_with_undecodable_token_still_records_an_accurate_audit_entry(mocker):
    # The HTTP response is a lenient 200 either way, but the security
    # audit trail must still distinguish "ended a resolvable session" from
    # "presented a token we couldn't even identify": success=False here is
    # what an operator reviewing the audit log needs to see, even though
    # the caller-facing outcome looks identical.
    _mock_decode(mocker, email=None)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    await logout_handler.handle_logout("garbage-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["success"] is False
    assert kwargs["user_email"] is None


@pytest.mark.asyncio
async def test_logout_success_records_an_accurate_audit_entry(mocker):
    _mock_decode(mocker)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    await logout_handler.handle_logout("valid-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_logout_records_the_resolved_email_in_the_audit_entry(mocker):
    # Regression guard: this handler used to never pass user_email to
    # log_security_event, so every logout row in the security audit log
    # showed no email regardless of who logged out (unlike login/
    # logout-all, which do resolve and record it).
    _mock_decode(mocker, email="user@example.com", jti="jti-1")
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)
    revoke_mock = mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)

    await logout_handler.handle_logout("valid-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["user_email"] == "user@example.com"
    # The session-ending call itself must get the email too, since ending
    # this device's session means bumping *that device's chain* version,
    # which needs to know whose account it belongs to.
    revoke_mock.assert_awaited_once_with(None, "jti-1", "user@example.com")


@pytest.mark.asyncio
async def test_logout_with_undecodable_token_records_audit_entry_with_no_email(mocker):
    _mock_decode(mocker, email=None)
    mocker.patch(f"{MODULE}.session_service.revoke_session_on_logout", new_callable=AsyncMock, return_value=True)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    await logout_handler.handle_logout("garbage-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["user_email"] is None
