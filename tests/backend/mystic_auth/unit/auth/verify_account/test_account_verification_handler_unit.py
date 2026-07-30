# tests/backend/mystic_auth/unit/test_account_verification_handler_unit.py
#
# account_verification_handler.py had no dedicated unit coverage. These tests
# pin down its lockout key namespace: it must be distinct from login's
# "login_lock:email:" key, or a burst of failed verification attempts (e.g. a
# double-submitted, already-consumed link racing the single-use check) would
# count towards and could trip the unrelated login lockout for the same email.
import pytest
from backend.mystic_auth.auth.verify_account.account_verification_handler import (
    account_verification_handler,
)

MODULE = "backend.mystic_auth.auth.verify_account.account_verification_handler"


@pytest.mark.asyncio
async def test_invalid_token_returns_400_without_touching_lockout(mocker):
    mocker.patch(f"{MODULE}.account_verification_service.verify_token", return_value=None)
    record_mock = mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action")

    response = await account_verification_handler.handle_account_verification(
        token="bad-token", db=None
    )

    assert response.status_code == 400
    record_mock.assert_not_called()


@pytest.mark.asyncio
async def test_successful_verification_is_recorded_under_its_own_lock_namespace(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.verify_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.user_verification_service.mark_user_verified", return_value=True)
    record_mock = mocker.patch(
        f"{MODULE}.login_protection_service.check_and_record_action", return_value=True
    )

    response = await account_verification_handler.handle_account_verification(
        token="valid-token", db=None
    )

    assert response.status_code == 200
    record_mock.assert_awaited_once_with(
        "verify_account_lock:email:user@example.com", success=True
    )


@pytest.mark.asyncio
async def test_already_verified_failure_is_recorded_under_its_own_lock_namespace_not_logins(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.verify_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.user_verification_service.mark_user_verified", return_value=False)
    record_mock = mocker.patch(
        f"{MODULE}.login_protection_service.check_and_record_action", return_value=True
    )

    response = await account_verification_handler.handle_account_verification(
        token="valid-token", db=None
    )

    assert response.status_code == 400
    key_used = record_mock.await_args.args[0]
    assert key_used == "verify_account_lock:email:user@example.com"
    assert key_used != "login_lock:email:user@example.com"


@pytest.mark.asyncio
async def test_lockout_from_repeated_failures_returns_429(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.verify_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.user_verification_service.mark_user_verified", return_value=False)
    mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action", return_value=False)

    response = await account_verification_handler.handle_account_verification(
        token="valid-token", db=None
    )

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_verification_email_request_always_returns_generic_200(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.send_verification_email_if_needed",
        return_value=False,
    )

    response = await account_verification_handler.handle_verification_email_request(
        email="missing@example.com", db=None
    )

    assert response.status_code == 200
    assert response.body


@pytest.mark.asyncio
async def test_verification_email_request_logs_only_when_email_is_sent(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.send_verification_email_if_needed",
        return_value=True,
    )
    log_mock = mocker.patch(f"{MODULE}.log_security_event")

    response = await account_verification_handler.handle_verification_email_request(
        email="user@example.com", db="fake-db"
    )

    assert response.status_code == 200
    log_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_verification_email_request_does_not_log_unsent_request(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.send_verification_email_if_needed",
        return_value=False,
    )
    log_mock = mocker.patch(f"{MODULE}.log_security_event")

    response = await account_verification_handler.handle_verification_email_request(
        email="verified@example.com", db="fake-db"
    )

    assert response.status_code == 200
    log_mock.assert_not_called()
