# Pins down account_verification_handler.py's lockout key namespace: it
# must be distinct from login's "login_lock:email:" key, or a burst of
# failed verification attempts (e.g. a double-submitted, already-consumed
# link racing the single-use check) could trip the unrelated login
# lockout for the same email.
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
    mocker.patch(f"{MODULE}.account_verification_service.consume_token", return_value=True)
    mocker.patch(f"{MODULE}.user_verification_service.mark_user_verified", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")
    record_mock = mocker.patch(f"{MODULE}.login_protection_service.check_and_record_action")

    response = await account_verification_handler.handle_account_verification(
        token="valid-token", db=None
    )

    assert response.status_code == 200
    record_mock.assert_not_called()


@pytest.mark.asyncio
async def test_already_verified_failure_is_recorded_under_its_own_lock_namespace_not_logins(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.verify_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.account_verification_service.consume_token", return_value=True)
    mocker.patch(f"{MODULE}.user_verification_service.mark_user_verified", return_value=False)
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    finish_mock = mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")

    response = await account_verification_handler.handle_account_verification(
        token="valid-token", db=None
    )

    assert response.status_code == 400
    finish_mock.assert_awaited_once_with("verify_account_lock:email:user@example.com", success=False)


@pytest.mark.asyncio
async def test_lockout_from_repeated_failures_returns_429(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.verify_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.account_verification_service.consume_token", return_value=True)
    mocker.patch(f"{MODULE}.user_verification_service.mark_user_verified", return_value=False)
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=True)
    mocker.patch(f"{MODULE}.login_protection_service.finish_protected_action")
    mocker.patch(f"{MODULE}.login_protection_service.is_locked", return_value=True)

    response = await account_verification_handler.handle_account_verification(
        token="valid-token", db=None
    )

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_locked_verification_is_rejected_before_account_mutation(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.verify_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.login_protection_service.begin_protected_action", return_value=False)
    verify_mock = mocker.patch(f"{MODULE}.user_verification_service.mark_user_verified")

    response = await account_verification_handler.handle_account_verification(
        token="valid-token", db=None
    )

    assert response.status_code == 429
    verify_mock.assert_not_called()


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
async def test_verification_email_request_logs_successful_delivery(mocker):
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
    assert log_mock.await_args.kwargs["success"] is True


@pytest.mark.asyncio
async def test_verification_email_request_logs_unsent_request_without_email_identity(mocker):
    mocker.patch(
        f"{MODULE}.account_verification_service.send_verification_email_if_needed",
        return_value=False,
    )
    log_mock = mocker.patch(f"{MODULE}.log_security_event")

    response = await account_verification_handler.handle_verification_email_request(
        email="verified@example.com", db="fake-db"
    )

    assert response.status_code == 200
    log_mock.assert_awaited_once()
    assert log_mock.await_args.kwargs["success"] is False
    assert log_mock.await_args.kwargs["user_email"] is None
