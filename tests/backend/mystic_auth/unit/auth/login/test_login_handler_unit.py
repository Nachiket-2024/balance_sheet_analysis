import json
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.login.login_handler import login_handler
from backend.mystic_auth.auth.security.login_protection_service import (
    login_protection_service,
)
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
    # A failed login must be recorded with success=False so it counts
    # towards the lockout threshold, for both the email and IP counters.
    record_mock.assert_any_call("login_lock:email:test@example.com", success=False)
    record_mock.assert_any_call(
        "login_lock:ip:unknown",
        success=False,
        max_attempts=login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP,
        lockout_time=login_protection_service.LOGIN_LOCKOUT_TIME_PER_IP,
    )


@pytest.mark.asyncio
async def test_locked_source_ip_is_rejected_before_authentication_even_if_email_is_not_locked(mocker):
    # A different email tried from the same abusive IP must still be
    # blocked by the IP-keyed counter even though that specific email has
    # never failed before: this is the credential-stuffing gap an
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
async def test_new_lockout_emits_one_real_time_security_alert(mocker):
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
        return_value=None,
    )
    alert_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.capture_security_alert",
        new_callable=AsyncMock,
    )

    response = await login_handler.handle_login(email="victim@example.com", password="wrong-password")

    assert response.status_code == 429
    alert_mock.assert_awaited_once_with(
        "account_locked",
        metadata={
            "lock_scope": "account",
            "target_email": "victim@example.com",
            "source_ip": "unknown",
            "request_id": "",
        },
    )


@pytest.mark.asyncio
async def test_pre_check_and_post_check_lockout_responses_are_identical(mocker):
    # Both lockout rejections (pre-auth pre-check and post-auth recheck)
    # share a single response builder so they can't drift apart.
    # get_remaining_seconds is pinned to the same value for both calls so
    # this test isolates "do the two paths build the same response", not
    # whether the real lockout key has the same TTL both times (that's
    # test_locked_account_response_reports_correct_retry_time below).
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.get_remaining_seconds",
        return_value=120,
    )
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
async def test_locked_account_response_reports_correct_retry_time(mocker):
    # A locked-out caller needs to know how long to wait, not just that
    # they're locked out, so this is surfaced both ways (Retry-After
    # header and the body's params.minutes for the login form's
    # translated message).
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=True,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.get_remaining_seconds",
        return_value=125,
    )
    login_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_service.login",
    )

    response = await login_handler.handle_login(email="test@example.com", password="whatever")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "125"
    body = json.loads(response.body)
    assert body["code"] == "ACCOUNT_LOCKED"
    # 125 seconds rounds up to 3 minutes, never down: telling a caller "2
    # minutes" when 2 minutes 5 seconds actually remain would have them
    # retry too early.
    assert body["params"]["minutes"] == 3
    login_mock.assert_not_called()


@pytest.mark.asyncio
async def test_locked_account_retry_time_never_reports_zero_minutes(mocker):
    # A near-expired lockout (a handful of seconds left, or the TTL key
    # already expired between the caller's is_locked check and this one)
    # must still tell the caller to wait at least a minute, not "try again
    # in 0 minutes", which reads as "you're not actually locked out."
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
        return_value=True,
    )
    mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.get_remaining_seconds",
        return_value=0,
    )

    response = await login_handler.handle_login(email="test@example.com", password="whatever")

    body = json.loads(response.body)
    assert body["params"]["minutes"] == 1


@pytest.mark.asyncio
async def test_missing_credentials_returns_400_without_touching_lockout(mocker):
    is_locked_mock = mocker.patch(
        "backend.mystic_auth.auth.login.login_handler.login_protection_service.is_locked",
    )

    response = await login_handler.handle_login(email="", password="")

    assert response.status_code == 400
    is_locked_mock.assert_not_called()
