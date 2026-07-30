# tests/backend/mystic_auth/unit/test_logout_handler_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.logout.logout_handler import logout_handler

MODULE = "backend.mystic_auth.auth.logout.logout_handler"


def _set_cookie_headers(response) -> list[str]:
    return [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]


@pytest.mark.asyncio
async def test_logout_without_refresh_token_returns_400(mocker):
    revoke_mock = mocker.patch(f"{MODULE}.refresh_token_service.revoke_refresh_token", new_callable=AsyncMock)

    response = await logout_handler.handle_logout(None)

    assert response.status_code == 400
    revoke_mock.assert_not_called()


@pytest.mark.asyncio
async def test_logout_with_already_revoked_token_still_succeeds_and_clears_cookies(mocker):
    # Regression guard: this is exactly what a stale/dead refresh-token
    # cookie looks like right after a password change (which revokes every
    # refresh token for the account) : the presented cookie is already
    # revoked, so revoke_refresh_token returns False. That must not be
    # treated as an error: the caller's goal (no valid session left in this
    # browser) is already true, so logout should still report success and
    # clear both cookies, not leave the frontend stuck showing "logged in"
    # with a dead cookie it can never successfully log out of.
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_refresh_token", new_callable=AsyncMock, return_value=False)

    response = await logout_handler.handle_logout("already-revoked-token")

    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_success_clears_both_cookies(mocker):
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_refresh_token", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout("valid-token")

    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_clears_refresh_token_cookie_with_matching_auth_path(mocker):
    # Regression guard: refresh_token is set with path="/auth"
    # (token_cookie_handler.py). A delete_cookie call without the same path
    # creates a *different* cookie the browser expires immediately, leaving
    # the real, still-valid "/auth"-scoped refresh_token cookie behind.
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_refresh_token", new_callable=AsyncMock, return_value=True)

    response = await logout_handler.handle_logout("valid-token")

    headers = _set_cookie_headers(response)
    refresh_header = next(h for h in headers if h.startswith("refresh_token="))
    assert "Path=/auth" in refresh_header


@pytest.mark.asyncio
async def test_logout_with_already_revoked_token_still_clears_refresh_cookie_with_matching_auth_path(mocker):
    # Same regression guard as above, specifically for the already-revoked
    # path : a fix that clears cookies but forgets the matching path=/auth
    # would silently reintroduce the original bug for this exact scenario.
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_refresh_token", new_callable=AsyncMock, return_value=False)

    response = await logout_handler.handle_logout("already-revoked-token")

    headers = _set_cookie_headers(response)
    refresh_header = next(h for h in headers if h.startswith("refresh_token="))
    assert "Path=/auth" in refresh_header


@pytest.mark.asyncio
async def test_logout_with_already_revoked_token_still_records_an_accurate_audit_entry(mocker):
    # The HTTP response is now a lenient 200 either way (see above), but the
    # security audit trail must still distinguish "revoked a live token"
    # from "presented one that was already dead" : success=False here is
    # what a real operator reviewing the audit log needs to see, even
    # though the caller-facing outcome looks identical.
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_refresh_token", new_callable=AsyncMock, return_value=False)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    await logout_handler.handle_logout("already-revoked-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["success"] is False


@pytest.mark.asyncio
async def test_logout_success_records_an_accurate_audit_entry(mocker):
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_refresh_token", new_callable=AsyncMock, return_value=True)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    await logout_handler.handle_logout("valid-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["success"] is True
