# tests/backend/mystic_auth/unit/test_password_reset_confirm_handler_unit.py
#
# password_reset_confirm_handler.py had no dedicated unit coverage. These
# tests pin down its lockout key namespace: it must be distinct from login's
# "login_lock:email:" key, or failures unrelated to a real login attempt
# (weak new password, reused old password, stale token) would count towards
# and could trip the unrelated login lockout for the same email.
import pytest
from backend.mystic_auth.auth.password_reset_confirm.password_reset_confirm_handler import (
    password_reset_confirm_handler,
)

MODULE = "backend.mystic_auth.auth.password_reset_confirm.password_reset_confirm_handler"


@pytest.mark.asyncio
async def test_invalid_token_returns_400_without_touching_lockout(mocker):
    mocker.patch(f"{MODULE}.jwt_service.verify_token", return_value=None)
    record_mock = mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action")

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="bad-token", new_password="NewStrongPass123!", db=None
    )

    assert response.status_code == 400
    record_mock.assert_not_called()


@pytest.mark.asyncio
async def test_successful_reset_is_recorded_under_its_own_lock_namespace(mocker):
    mocker.patch(f"{MODULE}.jwt_service.verify_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.password_reset_service.reset_password", return_value=True)
    record_mock = mocker.patch(
        f"{MODULE}.login_protection_service.check_and_record_action", return_value=True
    )

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="NewStrongPass123!", db=None
    )

    assert response.status_code == 200
    record_mock.assert_awaited_once_with(
        "password_reset_confirm_lock:email:user@example.com", success=True
    )


@pytest.mark.asyncio
async def test_failed_reset_is_recorded_under_its_own_lock_namespace_not_logins(mocker):
    mocker.patch(f"{MODULE}.jwt_service.verify_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.password_reset_service.reset_password", return_value=False)
    record_mock = mocker.patch(
        f"{MODULE}.login_protection_service.check_and_record_action", return_value=True
    )

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="weak", db=None
    )

    assert response.status_code == 400
    key_used = record_mock.await_args.args[0]
    assert key_used == "password_reset_confirm_lock:email:user@example.com"
    assert key_used != "login_lock:email:user@example.com"


@pytest.mark.asyncio
async def test_lockout_from_repeated_failures_returns_429(mocker):
    mocker.patch(f"{MODULE}.jwt_service.verify_token", return_value={"email": "user@example.com"})
    mocker.patch(f"{MODULE}.password_reset_service.reset_password", return_value=False)
    mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action", return_value=False)

    response = await password_reset_confirm_handler.handle_password_reset_confirm(
        token="valid-token", new_password="weak", db=None
    )

    assert response.status_code == 429
