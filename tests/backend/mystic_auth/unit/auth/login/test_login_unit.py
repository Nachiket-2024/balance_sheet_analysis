# tests/backend/mystic_auth/unit/test_login_unit.py
import pytest
from backend.mystic_auth.auth.login.login_handler import login_handler
from backend.mystic_auth.auth.security.login_protection_service import login_protection_service
from backend.mystic_auth.auth.token_logic.token_schema import TokenPairResponseSchema

VALID_TOKENS = TokenPairResponseSchema(access_token="access", refresh_token="refresh")


@pytest.mark.asyncio
async def test_login_success_sets_cookies_and_resets_lockout_counter(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=False,
    )
    reset_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.check_and_record_action",
        return_value=True,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_service.login",
        return_value=VALID_TOKENS,
    )

    response = await login_handler.handle_login(email="test@example.com", password="Test123!")

    assert response.status_code == 200
    assert "access_token" in response.headers.get("set-cookie", "")
    # Both the email-keyed and the IP-keyed counters must be reset on success
    reset_mock.assert_any_call("login_lock:email:test@example.com", success=True)
    reset_mock.assert_any_call(
        "login_lock:ip:unknown",
        success=True,
        max_attempts=login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP,
        lockout_time=login_protection_service.LOGIN_LOCKOUT_TIME_PER_IP,
    )


@pytest.mark.asyncio
async def test_failed_login_is_recorded_towards_lockout(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=False,
    )
    record_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.check_and_record_action",
        return_value=True,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_service.login",
        return_value=None,
    )

    response = await login_handler.handle_login(email="test@example.com", password="wrong-password")

    assert response.status_code == 401
    # The bug this guards against: a failed login must be recorded with
    # success=False so it counts towards the lockout threshold, instead of
    # being skipped entirely : for both the email and IP counters.
    record_mock.assert_any_call("login_lock:email:test@example.com", success=False)
    record_mock.assert_any_call(
        "login_lock:ip:unknown",
        success=False,
        max_attempts=login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP,
        lockout_time=login_protection_service.LOGIN_LOCKOUT_TIME_PER_IP,
    )


@pytest.mark.asyncio
async def test_locked_source_ip_is_rejected_before_authentication_even_if_email_is_not_locked(mocker):
    # A different email tried from the same abusive IP must still be blocked
    # by the IP-keyed counter even though that specific email has never
    # failed before : this is the credential-stuffing/spraying gap the
    # email-only lockout could never see.
    def is_locked_side_effect(key, *args, **kwargs):
        return key.startswith("login_lock:ip:")

    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        side_effect=is_locked_side_effect,
    )
    login_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_service.login",
    )

    response = await login_handler.handle_login(email="never-tried-before@example.com", password="whatever")

    assert response.status_code == 429
    login_mock.assert_not_called()


@pytest.mark.asyncio
async def test_locked_account_is_rejected_before_authentication_is_attempted(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=True,
    )
    login_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_service.login",
    )

    response = await login_handler.handle_login(email="test@example.com", password="Test123!")

    assert response.status_code == 429
    login_mock.assert_not_called()


@pytest.mark.asyncio
async def test_correct_password_is_still_rejected_once_locked(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=False,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.check_and_record_action",
        return_value=False,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_service.login",
        return_value=VALID_TOKENS,
    )

    response = await login_handler.handle_login(email="test@example.com", password="Test123!")

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_pre_check_and_post_check_lockout_responses_are_identical(mocker):
    # Both lockout rejections (pre-auth pre-check and post-auth recheck) share
    # a single response builder specifically so they can't drift apart.
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=True,
    )
    pre_check_response = await login_handler.handle_login(email="test@example.com", password="Test123!")

    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=False,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.check_and_record_action",
        return_value=False,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_service.login",
        return_value=VALID_TOKENS,
    )
    post_check_response = await login_handler.handle_login(email="test@example.com", password="Test123!")

    assert pre_check_response.status_code == post_check_response.status_code == 429
    assert pre_check_response.body == post_check_response.body


@pytest.mark.asyncio
async def test_missing_credentials_returns_400_without_touching_lockout(mocker):
    is_locked_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
    )

    response = await login_handler.handle_login(email="", password="")

    assert response.status_code == 400
    is_locked_mock.assert_not_called()
