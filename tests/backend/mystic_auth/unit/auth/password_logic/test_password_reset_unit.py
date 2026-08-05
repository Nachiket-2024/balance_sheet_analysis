# tests/backend/mystic_auth/unit/test_password_reset_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.password_logic.password_reset_service import password_reset_service

MODULE = "backend.mystic_auth.auth.password_logic.password_reset_service"


class _FakeUser:
    def __init__(self, hashed_password="old-hash"):
        self.hashed_password = hashed_password


# ---------------------------- send_reset_email ----------------------------

@pytest.mark.asyncio
async def test_send_reset_email_persists_single_use_token_in_redis(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.password_service.create_reset_token", return_value="reset-token-abc")
    mocker.patch(f"{MODULE}.send_email_task.kiq", new_callable=AsyncMock)
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)

    result = await password_reset_service.send_reset_email("user@example.com", db=None)

    assert result is True
    set_mock.assert_awaited_once()
    args, kwargs = set_mock.call_args
    assert args[0] == "password_reset:reset-token-abc"
    assert kwargs["ex"] > 0


@pytest.mark.asyncio
async def test_send_reset_email_returns_false_for_unknown_user(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=None)
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)

    result = await password_reset_service.send_reset_email("nobody@example.com", db=None)

    assert result is False
    set_mock.assert_not_called()


# ---------------------------- reset_password ----------------------------
#
# reset_password now consumes the Redis single-use entry atomically via
# GETDEL (rather than a separate GET followed by a later DELETE) to close a
# TOCTOU race where two concurrent requests with the same token could both
# pass the check before either consumed it. A request that wins the GETDEL
# but then fails a recoverable validation step restores the entry via
# `redis_client.set` so the user can retry with the same link, see
# password_reset_service.py's docstring for the full rationale.

FUTURE_EXP = 9999999999.0  # far-future JWT "exp" claim for restore-TTL math


@pytest.mark.asyncio
async def test_reset_password_succeeds_and_consumes_token(mocker):
    mocker.patch(
        f"{MODULE}.password_service.verify_reset_token",
        return_value={"email": "user@example.com", "exp": FUTURE_EXP},
    )
    getdel_mock = mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value="1")
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.password_service.validate_password_strength", return_value=True)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.password_service.verify_password", return_value=False)
    mocker.patch(f"{MODULE}.password_service.hash_password", return_value="new-hash")
    mocker.patch(f"{MODULE}.user_crud.update_by_email", return_value=True)
    revoke_all_mock = mocker.patch(
        f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock
    )

    result = await password_reset_service.reset_password("valid-token", "NewPass123!", db=None)

    assert result is True
    getdel_mock.assert_awaited_once_with("password_reset:valid-token")
    # A successful reset must never restore the token.
    set_mock.assert_not_called()
    # A successful reset must invalidate any session an attacker who stole
    # the account may already hold.
    revoke_all_mock.assert_awaited_once_with("user@example.com", None)


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_or_already_used_token(mocker):
    mocker.patch(
        f"{MODULE}.password_service.verify_reset_token",
        return_value={"email": "user@example.com", "exp": FUTURE_EXP},
    )
    mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value=None)
    update_mock = mocker.patch(f"{MODULE}.user_crud.update_by_email")

    result = await password_reset_service.reset_password("replayed-token", "NewPass123!", db=None)

    assert result is False
    # A token that GETDEL didn't find (never issued, expired, or already
    # redeemed) must never reach the actual password update.
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_reset_password_rejects_invalid_jwt_before_touching_redis(mocker):
    mocker.patch(f"{MODULE}.password_service.verify_reset_token", return_value=None)
    redis_getdel_mock = mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock)

    result = await password_reset_service.reset_password("garbage-token", "NewPass123!", db=None)

    assert result is False
    redis_getdel_mock.assert_not_called()


@pytest.mark.asyncio
async def test_reset_password_concurrent_replay_only_lets_one_request_through(mocker):
    # The core TOCTOU fix: GETDEL is atomic, so of two concurrent requests
    # presenting the same token, at most one can ever see a truthy result.
    mocker.patch(
        f"{MODULE}.password_service.verify_reset_token",
        return_value={"email": "user@example.com", "exp": FUTURE_EXP},
    )
    # First caller wins the atomic fetch-and-delete; a second, concurrent
    # caller racing it finds the key already gone.
    mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, side_effect=["1", None])
    mocker.patch(f"{MODULE}.password_service.validate_password_strength", return_value=True)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.password_service.verify_password", return_value=False)
    mocker.patch(f"{MODULE}.password_service.hash_password", return_value="new-hash")
    mocker.patch(f"{MODULE}.user_crud.update_by_email", return_value=True)
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock)

    first_result = await password_reset_service.reset_password("valid-token", "FirstPass123!", db=None)
    second_result = await password_reset_service.reset_password("valid-token", "SecondPass456!", db=None)

    assert first_result is True
    assert second_result is False


@pytest.mark.asyncio
async def test_reset_password_weak_password_restores_token_for_retry(mocker):
    mocker.patch(
        f"{MODULE}.password_service.verify_reset_token",
        return_value={"email": "user@example.com", "exp": FUTURE_EXP},
    )
    mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value="1")
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.password_service.validate_password_strength", return_value=False)

    result = await password_reset_service.reset_password("valid-token", "weak", db=None)

    assert result is False
    # A validation failure (as opposed to an actual successful reset) must
    # restore the token so the user can retry with a better password.
    set_mock.assert_awaited_once()
    args, kwargs = set_mock.call_args
    assert args[0] == "password_reset:valid-token"
    assert kwargs["ex"] > 0


@pytest.mark.asyncio
async def test_reset_password_same_as_old_password_restores_token_for_retry(mocker):
    mocker.patch(
        f"{MODULE}.password_service.verify_reset_token",
        return_value={"email": "user@example.com", "exp": FUTURE_EXP},
    )
    mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value="1")
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.password_service.validate_password_strength", return_value=True)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.password_service.verify_password", return_value=True)

    result = await password_reset_service.reset_password("valid-token", "SamePass123!", db=None)

    assert result is False
    set_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_password_db_failure_restores_token_for_retry(mocker):
    mocker.patch(
        f"{MODULE}.password_service.verify_reset_token",
        return_value={"email": "user@example.com", "exp": FUTURE_EXP},
    )
    mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value="1")
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.password_service.validate_password_strength", return_value=True)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.password_service.verify_password", return_value=False)
    mocker.patch(f"{MODULE}.password_service.hash_password", return_value="new-hash")
    mocker.patch(f"{MODULE}.user_crud.update_by_email", return_value=False)

    result = await password_reset_service.reset_password("valid-token", "NewPass123!", db=None)

    assert result is False
    set_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_password_restore_ttl_is_capped_by_remaining_jwt_lifetime(mocker):
    # The restored key's TTL must never outlive the token's own JWT expiry,
    # otherwise a persistent series of failed retries could keep the Redis
    # entry alive indefinitely regardless of the token's real expiration.
    import time

    near_future_exp = time.time() + 30  # ~30s of real remaining lifetime
    mocker.patch(
        f"{MODULE}.password_service.verify_reset_token",
        return_value={"email": "user@example.com", "exp": near_future_exp},
    )
    mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value="1")
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.password_service.validate_password_strength", return_value=False)

    await password_reset_service.reset_password("valid-token", "weak", db=None)

    args, kwargs = set_mock.call_args
    assert 0 < kwargs["ex"] <= 31
