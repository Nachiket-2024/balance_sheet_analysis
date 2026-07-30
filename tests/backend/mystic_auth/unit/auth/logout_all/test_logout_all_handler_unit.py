# tests/backend/mystic_auth/unit/test_logout_all_handler_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.logout_all.logout_all_handler import logout_all_handler

MODULE = "backend.mystic_auth.auth.logout_all.logout_all_handler"


def _set_cookie_headers(response) -> list[str]:
    return [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]


@pytest.mark.asyncio
async def test_logout_all_without_refresh_token_returns_400(mocker):
    decode_mock = mocker.patch(f"{MODULE}.jwt_service.decode_payload", new_callable=AsyncMock)

    response = await logout_all_handler.handle_logout_all(None)

    assert response.status_code == 400
    decode_mock.assert_not_called()


@pytest.mark.asyncio
async def test_logout_all_with_undecodable_token_still_succeeds_and_clears_cookies(mocker):
    # A token that fails to decode at all (malformed, wrong signature, or
    # simply garbage) carries no recoverable email, so there's nothing left
    # to revoke server-side : but the caller's goal (no valid session left
    # in this browser) is still met, so this must clear cookies and report
    # success rather than error out.
    mocker.patch(f"{MODULE}.jwt_service.decode_payload", new_callable=AsyncMock, return_value=None)
    revoke_mock = mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock)

    response = await logout_all_handler.handle_logout_all("garbage-token")

    assert response.status_code == 200
    revoke_mock.assert_not_called()
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_all_with_wrong_type_token_does_not_revoke_but_still_clears_cookies(mocker):
    # decode_payload skips the revocation check (unlike verify_token), but
    # must not also skip the "type" claim check : a wrong-type token (e.g.
    # an access token mistakenly presented as the refresh_token cookie) must
    # never be treated as resolving a real email to revoke sessions for,
    # same as refresh_tokens() in refresh_token_service.py. It still clears
    # cookies and reports success, consistent with every other invalid-token
    # case here.
    mocker.patch(
        f"{MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "access"},
    )
    revoke_mock = mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock)

    response = await logout_all_handler.handle_logout_all("access-token-in-refresh-cookie")

    revoke_mock.assert_not_called()
    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_all_with_already_revoked_token_still_resolves_email_and_revokes_remaining_sessions(mocker):
    # Regression guard: right after a password change (which revokes every
    # refresh token for the account), this device's own refresh-token cookie
    # is already revoked. jwt_service.verify_token would reject it outright
    # (no email recoverable), but decode_payload : which skips the
    # revocation check, same as reuse-detection in refresh_token_service :
    # still yields the owning email, so logout-all can still revoke whatever
    # sessions remain and clear cookies instead of erroring out.
    mocker.patch(
        f"{MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "refresh"},
    )
    revoke_mock = mocker.patch(
        f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=2
    )

    response = await logout_all_handler.handle_logout_all("already-revoked-token")

    revoke_mock.assert_awaited_once_with("user@example.com")
    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_all_with_no_active_sessions_still_succeeds_and_clears_cookies(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "refresh"},
    )
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=0)

    response = await logout_all_handler.handle_logout_all("valid-token")

    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_all_success_clears_both_cookies(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "refresh"},
    )
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=3)

    response = await logout_all_handler.handle_logout_all("valid-token")

    assert response.status_code == 200
    headers = _set_cookie_headers(response)
    assert any(h.startswith("access_token=") for h in headers)
    assert any(h.startswith("refresh_token=") for h in headers)


@pytest.mark.asyncio
async def test_logout_all_clears_refresh_token_cookie_with_matching_auth_path(mocker):
    # Same regression guard as logout_handler: the delete must specify
    # path="/auth" to actually clear the cookie token_cookie_handler set.
    mocker.patch(
        f"{MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "refresh"},
    )
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=1)

    response = await logout_all_handler.handle_logout_all("valid-token")

    headers = _set_cookie_headers(response)
    refresh_header = next(h for h in headers if h.startswith("refresh_token="))
    assert "Path=/auth" in refresh_header


@pytest.mark.asyncio
async def test_logout_all_with_already_revoked_token_still_records_an_accurate_audit_entry(mocker):
    # As with logout_handler: the HTTP response is now a lenient 200 either
    # way, but the audit trail must still record success=False (and the
    # resolved email, even from an already-revoked token) for a real
    # operator reviewing it later.
    mocker.patch(
        f"{MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "refresh"},
    )
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=0)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    await logout_all_handler.handle_logout_all("already-revoked-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["success"] is False
    assert kwargs["user_email"] == "user@example.com"


@pytest.mark.asyncio
async def test_logout_all_with_undecodable_token_records_audit_entry_with_no_email(mocker):
    # A token that fails to decode entirely has no recoverable email : the
    # audit entry must reflect that (None, not a crash trying to look one
    # up) rather than skipping the audit call altogether.
    mocker.patch(f"{MODULE}.jwt_service.decode_payload", new_callable=AsyncMock, return_value=None)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    await logout_all_handler.handle_logout_all("garbage-token")

    audit_mock.assert_awaited_once()
    _, kwargs = audit_mock.call_args
    assert kwargs["success"] is False
    assert kwargs["user_email"] is None
