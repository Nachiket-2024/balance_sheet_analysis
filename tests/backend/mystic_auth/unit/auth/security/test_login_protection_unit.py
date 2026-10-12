from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.security.login_protection_service import (
    login_protection_service,
)

MODULE = "backend.mystic_auth.auth.security.login_protection_service"


# ---------------------------- record_failed_attempt ----------------------------

@pytest.mark.asyncio
async def test_record_failed_attempt_uses_single_incr_without_a_prior_get(mocker):
    get_mock = mocker.patch(f"{MODULE}.valkey_client.get")
    incr_mock = mocker.patch(f"{MODULE}.valkey_client.incr", new_callable=AsyncMock, return_value=1)
    expire_mock = mocker.patch(f"{MODULE}.valkey_client.expire", new_callable=AsyncMock)

    await login_protection_service.record_failed_attempt("login_lock:email:user@example.com")

    # The old implementation did a GET purely to decide between SET and INCR;
    # INCR alone (atomic, auto-creates at 0) makes that redundant round-trip
    # unnecessary.
    get_mock.assert_not_called()
    incr_mock.assert_awaited_once_with("login_lock:email:user@example.com")
    expire_mock.assert_awaited_once_with(
        "login_lock:email:user@example.com", login_protection_service.LOGIN_LOCKOUT_TIME
    )


@pytest.mark.asyncio
async def test_record_failed_attempt_only_sets_expiry_on_first_failure(mocker):
    mocker.patch(f"{MODULE}.valkey_client.incr", new_callable=AsyncMock, return_value=3)
    expire_mock = mocker.patch(f"{MODULE}.valkey_client.expire", new_callable=AsyncMock)

    await login_protection_service.record_failed_attempt("login_lock:email:user@example.com")

    # Re-applying the TTL on every later failure would keep sliding the
    # lockout window forward instead of expiring LOGIN_LOCKOUT_TIME after
    # the first failure as intended.
    expire_mock.assert_not_called()


# ---------------------------- is_locked ----------------------------

@pytest.mark.asyncio
async def test_is_locked_true_once_count_reaches_threshold(mocker):
    mocker.patch(
        f"{MODULE}.valkey_client.get",
        new_callable=AsyncMock,
        return_value=str(login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS),
    )

    assert await login_protection_service.is_locked("key") is True


@pytest.mark.asyncio
async def test_is_locked_false_under_threshold(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value="1")

    assert await login_protection_service.is_locked("key") is False


@pytest.mark.asyncio
async def test_is_locked_fails_closed_on_valkey_error(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", side_effect=ConnectionError("valkey unreachable"))
    error_mock = mocker.patch(f"{MODULE}.logger.error")

    assert await login_protection_service.is_locked("key") is True
    error_mock.assert_called_once()


# ---------------------------- get_remaining_seconds ----------------------------

@pytest.mark.asyncio
async def test_get_remaining_seconds_returns_the_real_ttl(mocker):
    mocker.patch(f"{MODULE}.valkey_client.ttl", new_callable=AsyncMock, return_value=90)

    assert await login_protection_service.get_remaining_seconds("key") == 90


@pytest.mark.asyncio
async def test_get_remaining_seconds_floors_a_missing_key_at_zero(mocker):
    # valkey TTL returns -2 for a key that doesn't exist at all (already
    # expired, or never existed): a real possibility if this races the
    # key expiring naturally between the caller's is_locked check and
    # this call. There's nothing meaningful left to wait out either way.
    mocker.patch(f"{MODULE}.valkey_client.ttl", new_callable=AsyncMock, return_value=-2)

    assert await login_protection_service.get_remaining_seconds("key") == 0


@pytest.mark.asyncio
async def test_get_remaining_seconds_floors_a_key_with_no_expiry_at_zero(mocker):
    # valkey TTL returns -1 for a key that exists but was never given a
    # TTL. Shouldn't happen for a lockout key (record_failed_attempt
    # always sets one), but this must not surface as a negative wait
    # time if it ever did.
    mocker.patch(f"{MODULE}.valkey_client.ttl", new_callable=AsyncMock, return_value=-1)

    assert await login_protection_service.get_remaining_seconds("key") == 0


@pytest.mark.asyncio
async def test_get_remaining_seconds_returns_zero_on_valkey_error(mocker):
    mocker.patch(f"{MODULE}.valkey_client.ttl", side_effect=Exception("boom"))

    assert await login_protection_service.get_remaining_seconds("key") == 0


# ---------------------------- check_and_record_action ----------------------------

@pytest.mark.asyncio
async def test_begin_protected_action_uses_atomic_reservation(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=None)
    set_mock = mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock, return_value=True)

    assert await login_protection_service.begin_protected_action("key") is True
    set_mock.assert_awaited_once_with(
        "key:inflight", "1", ex=login_protection_service.ACTION_RESERVATION_TIME, nx=True
    )


@pytest.mark.asyncio
async def test_begin_protected_action_denies_when_reservation_is_taken(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock, return_value=None)

    assert await login_protection_service.begin_protected_action("key") is False


@pytest.mark.asyncio
async def test_begin_protected_action_denies_when_key_is_already_locked(mocker):
    mocker.patch(
        f"{MODULE}.valkey_client.get",
        new_callable=AsyncMock,
        return_value=str(login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS),
    )
    set_mock = mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock)

    assert await login_protection_service.begin_protected_action("key") is False
    set_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_begin_protected_action_fails_closed_when_reservation_write_errors(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock, side_effect=RuntimeError("down"))

    assert await login_protection_service.begin_protected_action("key") is False


@pytest.mark.asyncio
async def test_finish_protected_action_records_failure_and_releases_reservation(mocker):
    record_mock = mocker.patch(f"{MODULE}.LoginProtectionService.check_and_record_action", new_callable=AsyncMock, return_value=True)
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await login_protection_service.finish_protected_action("key", success=False)

    record_mock.assert_awaited_once_with("key", success=False)
    delete_mock.assert_awaited_once_with("key:inflight")


@pytest.mark.asyncio
async def test_release_protected_action_swallows_valkey_errors(mocker):
    mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock, side_effect=RuntimeError("down"))

    await login_protection_service.release_protected_action("key")


@pytest.mark.asyncio
async def test_reset_failed_attempts_swallows_valkey_errors(mocker):
    mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock, side_effect=RuntimeError("down"))

    await login_protection_service.reset_failed_attempts("key")


@pytest.mark.asyncio
async def test_check_and_record_action_returns_false_when_increment_fails(mocker):
    mocker.patch(f"{MODULE}.valkey_client.incr", new_callable=AsyncMock, side_effect=RuntimeError("down"))

    assert await login_protection_service.check_and_record_action("key", success=False) is False

@pytest.mark.asyncio
async def test_check_and_record_action_resets_on_success(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value="2")
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    allowed = await login_protection_service.check_and_record_action("key", success=True)

    assert allowed is True
    delete_mock.assert_awaited_once_with("key")


@pytest.mark.asyncio
async def test_check_and_record_action_records_failure_and_allows_under_threshold(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=None)
    incr_mock = mocker.patch(f"{MODULE}.valkey_client.incr", new_callable=AsyncMock, return_value=1)
    mocker.patch(f"{MODULE}.valkey_client.expire", new_callable=AsyncMock)

    allowed = await login_protection_service.check_and_record_action("key", success=False)

    assert allowed is True
    incr_mock.assert_awaited_once_with("key")


@pytest.mark.asyncio
async def test_check_and_record_action_denies_when_already_locked(mocker):
    mocker.patch(
        f"{MODULE}.valkey_client.get",
        new_callable=AsyncMock,
        return_value=str(login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS),
    )
    incr_mock = mocker.patch(f"{MODULE}.valkey_client.incr", new_callable=AsyncMock)
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    # Even a "successful" outcome must be denied once the account is
    # already locked: this race-safety check exists independently of any
    # pre-check a caller performed earlier.
    allowed = await login_protection_service.check_and_record_action("key", success=True)

    assert allowed is False
    incr_mock.assert_not_called()
    delete_mock.assert_not_called()


# ---------------------------- per-IP threshold/window overrides ----------------------------
# These support login_handler.py's additive IP-keyed counter, which
# aggregates failed attempts across any account from a single source IP,
# catching credential-stuffing/spraying that the email-keyed counter
# alone can't see, since no single email ever crosses its own threshold
# in that attack.

@pytest.mark.asyncio
async def test_is_locked_honors_a_custom_max_attempts_threshold(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value="5")

    # Below the custom (higher) IP threshold, even though it would already
    # exceed the default per-email threshold
    assert await login_protection_service.is_locked("login_lock:ip:1.2.3.4", max_attempts=20) is False


@pytest.mark.asyncio
async def test_record_failed_attempt_honors_a_custom_lockout_time(mocker):
    mocker.patch(f"{MODULE}.valkey_client.incr", new_callable=AsyncMock, return_value=1)
    expire_mock = mocker.patch(f"{MODULE}.valkey_client.expire", new_callable=AsyncMock)

    await login_protection_service.record_failed_attempt("login_lock:ip:1.2.3.4", lockout_time=999)

    expire_mock.assert_awaited_once_with("login_lock:ip:1.2.3.4", 999)


@pytest.mark.asyncio
async def test_check_and_record_action_uses_custom_threshold_and_window_for_ip_key(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=None)
    incr_mock = mocker.patch(f"{MODULE}.valkey_client.incr", new_callable=AsyncMock, return_value=1)
    expire_mock = mocker.patch(f"{MODULE}.valkey_client.expire", new_callable=AsyncMock)

    allowed = await login_protection_service.check_and_record_action(
        "login_lock:ip:1.2.3.4", success=False, max_attempts=20, lockout_time=999
    )

    assert allowed is True
    incr_mock.assert_awaited_once_with("login_lock:ip:1.2.3.4")
    expire_mock.assert_awaited_once_with("login_lock:ip:1.2.3.4", 999)
