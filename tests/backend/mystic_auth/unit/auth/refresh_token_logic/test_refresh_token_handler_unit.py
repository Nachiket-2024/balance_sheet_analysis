# Regression guard: refresh_token_service.refresh_tokens returns a plain
# dict[str, str], but the handler previously annotated it as
# TokenPairResponseSchema and accessed `.access_token` on it directly. A
# dict has no such attribute, so every successful refresh raised
# AttributeError and returned 500 instead of the new tokens. Only caught
# by a real integration test since every unit test here mocked at the
# service layer, never exercising the handler's consumption of the
# service's actual return type.
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.refresh_token_logic.refresh_token_handler import (
    refresh_token_handler,
)

HANDLER_MODULE = "backend.mystic_auth.auth.refresh_token_logic.refresh_token_handler"


class _FakeClient:
    host = "1.2.3.4"


class _FakeRequest:
    client = _FakeClient()


@pytest.mark.asyncio
async def test_handle_refresh_tokens_returns_200_with_new_tokens(mocker):
    mocker.patch(f"{HANDLER_MODULE}.rate_limiter_service.record_request", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{HANDLER_MODULE}.login_protection_service.is_locked", new_callable=AsyncMock, return_value=False)
    mocker.patch(f"{HANDLER_MODULE}.login_protection_service.reset_failed_attempts", new_callable=AsyncMock)
    mocker.patch(
        f"{HANDLER_MODULE}.refresh_token_service.refresh_tokens",
        new_callable=AsyncMock,
        return_value={"access_token": "new-access", "refresh_token": "new-refresh"},
    )

    response = await refresh_token_handler.handle_refresh_tokens(
        _FakeRequest(), "old-refresh"
    )

    assert response.status_code == 200
    assert "access_token" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_handle_refresh_tokens_rejects_invalid_token(mocker):
    mocker.patch(f"{HANDLER_MODULE}.rate_limiter_service.record_request", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{HANDLER_MODULE}.login_protection_service.is_locked", new_callable=AsyncMock, return_value=False)
    record_mock = mocker.patch(
        f"{HANDLER_MODULE}.login_protection_service.record_failed_attempt", new_callable=AsyncMock
    )
    mocker.patch(f"{HANDLER_MODULE}.refresh_token_service.refresh_tokens", new_callable=AsyncMock, return_value=None)

    with pytest.raises(Exception) as exc_info:
        await refresh_token_handler.handle_refresh_tokens(
            _FakeRequest(), "bad-token"
        )

    assert getattr(exc_info.value, "status_code", None) == 401
    record_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_refresh_tokens_rejects_missing_cookie_without_touching_valkey(mocker):
    # Regression guard: refresh_token is read from the httponly cookie by
    # the route (refresh_token_routes.py), not a JSON body. A client with
    # no session at all (cookie absent) must get the same 401 as an
    # invalid token, without spending a rate-limit/lockout Valkey
    # round-trip on a request that was never going anywhere.
    rate_mock = mocker.patch(f"{HANDLER_MODULE}.rate_limiter_service.record_request", new_callable=AsyncMock)

    with pytest.raises(Exception) as exc_info:
        await refresh_token_handler.handle_refresh_tokens(_FakeRequest(), None)

    assert getattr(exc_info.value, "status_code", None) == 401
    rate_mock.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limit_and_lockout_use_distinct_valkey_keys(mocker):
    # Regression guard: rate_key and lock_key were previously the
    # identical string "refresh:ip:{ip}". rate_limiter_service
    # .record_request (called on every request, success or failure) and
    # login_protection_service's failure counter shared that one key, so
    # a handful of legitimate refreshes alone could trip the 5-attempt
    # lockout with zero real failures. The two services must be given
    # independent key namespaces.
    rate_request_mock = mocker.patch(
        f"{HANDLER_MODULE}.rate_limiter_service.record_request", new_callable=AsyncMock, return_value=True
    )
    is_locked_mock = mocker.patch(
        f"{HANDLER_MODULE}.login_protection_service.is_locked", new_callable=AsyncMock, return_value=False
    )
    mocker.patch(f"{HANDLER_MODULE}.login_protection_service.reset_failed_attempts", new_callable=AsyncMock)
    mocker.patch(
        f"{HANDLER_MODULE}.refresh_token_service.refresh_tokens",
        new_callable=AsyncMock,
        return_value={"access_token": "new-access", "refresh_token": "new-refresh"},
    )

    await refresh_token_handler.handle_refresh_tokens(_FakeRequest(), "old-refresh")

    rate_key = rate_request_mock.call_args.args[0]
    lock_key = is_locked_mock.call_args.args[0]
    assert rate_key != lock_key
    assert "1.2.3.4" in rate_key
    assert "1.2.3.4" in lock_key


@pytest.mark.asyncio
async def test_refresh_lockout_is_also_keyed_by_account_not_just_ip(mocker):
    # Regression guard: the lockout here used to be keyed on client IP only
    # ("refresh:lockout:ip:{ip}"), unlike the login flow's own lockout
    # (keyed on *both* IP and email). Consequence: a leaked/stolen refresh
    # token for one victim account, replayed from many different IPs,
    # never accumulated enough failures on any single per-IP key to lock
    # out - there was no account-level backstop at all. This test pins
    # down that an account-scoped lock now exists and is actually
    # consulted: with the IP-keyed lock reporting "not locked" but the
    # account-keyed lock reporting "locked," the request must still be
    # rejected with 429, not fall through to the IP check's answer alone.
    mocker.patch(f"{HANDLER_MODULE}.rate_limiter_service.record_request", new_callable=AsyncMock, return_value=True)
    mocker.patch(
        f"{HANDLER_MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "victim@example.com", "type": "refresh"},
    )

    async def _is_locked(key: str) -> bool:
        return "account:victim@example.com" in key

    is_locked_mock = mocker.patch(
        f"{HANDLER_MODULE}.login_protection_service.is_locked", side_effect=_is_locked
    )

    with pytest.raises(Exception) as exc_info:
        await refresh_token_handler.handle_refresh_tokens(_FakeRequest(), "stolen-refresh-token")

    assert getattr(exc_info.value, "status_code", None) == 429
    checked_keys = [call.args[0] for call in is_locked_mock.call_args_list]
    assert any("ip:1.2.3.4" in k for k in checked_keys)
    assert any("account:victim@example.com" in k for k in checked_keys)


@pytest.mark.asyncio
async def test_refresh_failure_records_against_both_ip_and_account_locks(mocker):
    mocker.patch(f"{HANDLER_MODULE}.rate_limiter_service.record_request", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{HANDLER_MODULE}.login_protection_service.is_locked", new_callable=AsyncMock, return_value=False)
    mocker.patch(
        f"{HANDLER_MODULE}.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "victim@example.com", "type": "refresh"},
    )
    record_mock = mocker.patch(
        f"{HANDLER_MODULE}.login_protection_service.record_failed_attempt", new_callable=AsyncMock
    )
    mocker.patch(f"{HANDLER_MODULE}.refresh_token_service.refresh_tokens", new_callable=AsyncMock, return_value=None)

    with pytest.raises(Exception) as exc_info:
        await refresh_token_handler.handle_refresh_tokens(_FakeRequest(), "bad-token")

    assert getattr(exc_info.value, "status_code", None) == 401
    recorded_keys = [call.args[0] for call in record_mock.call_args_list]
    assert any("ip:1.2.3.4" in k for k in recorded_keys)
    assert any("account:victim@example.com" in k for k in recorded_keys)


@pytest.mark.asyncio
async def test_refresh_with_undecodable_token_only_uses_ip_lock(mocker):
    # A garbage/forged token (never validly signed) yields no email from
    # decode_payload, so there is nothing to key an account lock on - the
    # pre-existing IP-only behavior is the correct fallback for this case,
    # not a gap: an attacker guessing at tokens never had a real account's
    # token to begin with.
    mocker.patch(f"{HANDLER_MODULE}.rate_limiter_service.record_request", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{HANDLER_MODULE}.jwt_service.decode_payload", new_callable=AsyncMock, return_value=None)
    is_locked_mock = mocker.patch(
        f"{HANDLER_MODULE}.login_protection_service.is_locked", new_callable=AsyncMock, return_value=False
    )
    mocker.patch(f"{HANDLER_MODULE}.login_protection_service.reset_failed_attempts", new_callable=AsyncMock)
    mocker.patch(
        f"{HANDLER_MODULE}.refresh_token_service.refresh_tokens",
        new_callable=AsyncMock,
        return_value={"access_token": "new-access", "refresh_token": "new-refresh"},
    )

    await refresh_token_handler.handle_refresh_tokens(_FakeRequest(), "not-a-real-token")

    assert is_locked_mock.await_count == 1
    assert "ip:1.2.3.4" in is_locked_mock.call_args.args[0]
