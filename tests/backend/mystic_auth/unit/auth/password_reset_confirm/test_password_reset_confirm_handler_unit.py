# Pins down password_reset_confirm_handler.py's lockout key namespace: it
# must be distinct from login's "login_lock:email:" key, or failures
# unrelated to a real login attempt (weak new password, reused old
# password, stale token) could trip the unrelated login lockout for the
# same email.
import json

import pytest

from backend.mystic_auth.auth.password_reset_confirm.password_reset_confirm_handler import (
    password_reset_confirm_handler,
)

MODULE = "backend.mystic_auth.auth.password_reset_confirm.password_reset_confirm_handler"


@pytest.mark.asyncio
async def test_invalid_token_returns_400_without_touching_lockout(mocker):
    mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value=None)
    record_mock = mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action")

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="bad-token", new_password="NewStrongPass123!", db=None
    )

    assert response.status_code == 400
    record_mock.assert_not_called()


@pytest.mark.asyncio
async def test_non_reset_token_is_rejected_without_touching_lockout(mocker):
    """A validly-signed access/refresh/verify token for a victim's account
    must never reach the lockout path here: verify_reset_token (unlike a
    bare jwt_service.verify_token call) already rejects anything whose
    "type" claim isn't "reset", so this behaves like an invalid token."""
    verify_mock = mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value=None)
    record_mock = mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action")

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-access-token-wrong-type", new_password="NewStrongPass123!", db=None
    )

    assert response.status_code == 400
    verify_mock.assert_awaited_once_with("valid-access-token-wrong-type")
    record_mock.assert_not_called()


@pytest.mark.asyncio
async def test_successful_reset_is_recorded_under_its_own_lock_namespace(mocker):
    mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.password_reset_service.reset_password", return_value=(True, True))
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    finish_mock = mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="NewStrongPass123!", db=None
    )

    assert response.status_code == 200
    finish_mock.assert_awaited_once_with("password_reset_confirm_lock:email:user@example.com", success=True)


@pytest.mark.asyncio
async def test_successful_reset_reports_sessions_revoked_in_the_response_body(mocker):
    # Regression guard: reset_password's sessions_revoked flag (False
    # when the account-version bump couldn't be confirmed) must reach the
    # caller, since the point of this field is that a genuinely
    # successful reset can still leave the attacker's other sessions
    # unrevoked.
    mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.password_reset_service.reset_password", return_value=(True, False))
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="NewStrongPass123!", db=None
    )

    assert response.status_code == 200
    assert json.loads(response.body)["sessions_revoked"] is False


@pytest.mark.asyncio
async def test_failed_reset_is_recorded_under_its_own_lock_namespace_not_logins(mocker):
    mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.password_reset_service.reset_password", return_value=(False, None))
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    finish_mock = mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="weak", db=None
    )

    assert response.status_code == 400
    finish_mock.assert_awaited_once_with("password_reset_confirm_lock:email:user@example.com", success=False)


@pytest.mark.asyncio
async def test_lockout_from_repeated_failures_returns_429(mocker):
    mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.password_reset_service.reset_password", return_value=(False, None))
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")
    mocker.patch(f"{MODULE}.login_protection_service.is_locked", return_value=True)

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="weak", db=None
    )

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_locked_reset_is_rejected_before_password_mutation(mocker):
    mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=False)
    reset_mock = mocker.patch(f"{MODULE}.password_reset_service.reset_password")

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="NewStrongPass123!", db=None
    )

    assert response.status_code == 429
    reset_mock.assert_not_called()
