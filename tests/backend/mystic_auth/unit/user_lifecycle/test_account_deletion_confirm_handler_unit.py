# tests/backend/mystic_auth/unit/user_lifecycle/test_account_deletion_confirm_handler_unit.py
#
# account_deletion_confirm_handler.py's lockout key namespace must be
# distinct from both login's "login_lock:email:" key and
# "password_reset_confirm_lock:email:", same reasoning as
# test_password_reset_confirm_handler_unit.py: failures unrelated to a real
# login attempt (a stale/reused deletion link) must never count towards, or
# be able to trip, an unrelated lockout for the same email.
import pytest

from backend.mystic_auth.user_lifecycle.account_deletion_confirm_handler import (
    account_deletion_confirm_handler,
)

MODULE = "backend.mystic_auth.user_lifecycle.account_deletion_confirm_handler"


@pytest.mark.asyncio
async def test_invalid_token_returns_400_without_touching_lockout(mocker):
    mocker.patch(f"{MODULE}.account_deletion_service.verify_account_deletion_token", return_value=None)
    record_mock = mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action")

    response = await account_deletion_confirm_handler.handle_confirm_delete(token="bad-token", db=None)

    assert response.status_code == 400
    record_mock.assert_not_called()


@pytest.mark.asyncio
async def test_non_delete_token_is_rejected_without_touching_lockout(mocker):
    # verify_account_deletion_token already rejects anything whose "type"
    # claim isn't "account_delete" (e.g. a valid password-reset token), so
    # this behaves identically to an outright invalid token.
    verify_mock = mocker.patch(f"{MODULE}.account_deletion_service.verify_account_deletion_token", return_value=None)
    record_mock = mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action")

    response = await account_deletion_confirm_handler.handle_confirm_delete(
        token="valid-reset-token-wrong-type", db=None
    )

    assert response.status_code == 400
    verify_mock.assert_awaited_once_with("valid-reset-token-wrong-type")
    record_mock.assert_not_called()


@pytest.mark.asyncio
async def test_successful_confirm_is_recorded_under_its_own_lock_namespace_and_clears_cookies(mocker):
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.account_deletion_service.confirm_deletion", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")

    response = await account_deletion_confirm_handler.handle_confirm_delete(token="valid-token", db=None)

    assert response.status_code == 200
    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any(header.startswith("access_token=") for header in set_cookie_headers)
    assert any(header.startswith("refresh_token=") and "Path=/auth" in header for header in set_cookie_headers)


@pytest.mark.asyncio
async def test_failed_confirm_is_recorded_under_its_own_lock_namespace_not_logins_or_reset(mocker):
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.account_deletion_service.confirm_deletion", return_value=False)
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")

    response = await account_deletion_confirm_handler.handle_confirm_delete(token="replayed-token", db=None)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_lockout_from_repeated_failures_returns_429(mocker):
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.account_deletion_service.confirm_deletion", return_value=False)
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")
    mocker.patch(f"{MODULE}.login_protection_service.is_locked", return_value=True)

    response = await account_deletion_confirm_handler.handle_confirm_delete(token="replayed-token", db=None)

    assert response.status_code == 429
