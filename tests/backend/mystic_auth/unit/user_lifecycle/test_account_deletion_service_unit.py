# tests/backend/mystic_auth/unit/user_lifecycle/test_account_deletion_service_unit.py
#
# account_deletion_service.py is the async, email-confirmed self-service
# deletion flow for OAuth-only accounts (hashed_password is None), modeled
# directly on password_reset_service.py. These tests pin down: the token's
# own "account_delete" type claim (so it can't be swapped for a reset/
# access/refresh token), single-use/replay rejection via GETDEL, expiry, and
# that a successful confirm actually runs the shared soft-delete + revoke +
# audit sequence (finalize_self_deletion) exactly once.
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.user_lifecycle.account_deletion_service import (
    account_deletion_service,
)

MODULE = "backend.mystic_auth.user_lifecycle.account_deletion_service"


class _FakeUser:
    def __init__(self, email="user@example.com"):
        self.email = email


# ---------------------------- token create/verify ----------------------------

@pytest.mark.asyncio
async def test_deletion_token_round_trips_through_create_and_verify():
    token = await account_deletion_service.create_account_deletion_token("user@example.com")
    payload = await account_deletion_service.verify_account_deletion_token(token)

    assert payload is not None
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "account_delete"


@pytest.mark.asyncio
async def test_verify_deletion_token_rejects_token_missing_type_claim():
    import asyncio

    import jwt

    payload = {"email": "user@example.com", "exp": 9999999999.0}
    token = await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    assert await account_deletion_service.verify_account_deletion_token(token) is None


@pytest.mark.asyncio
async def test_verify_deletion_token_rejects_wrong_type_claim():
    # A validly-signed password-reset token (or access/refresh token) must
    # never be usable here: they share the same SECRET_KEY signature and
    # could otherwise carry an "email" claim too.
    import asyncio

    import jwt

    payload = {"email": "user@example.com", "type": "reset", "exp": 9999999999.0}
    token = await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    assert await account_deletion_service.verify_account_deletion_token(token) is None


@pytest.mark.asyncio
async def test_verify_deletion_token_rejects_expired_token():
    import asyncio

    import jwt

    payload = {"email": "user@example.com", "type": "account_delete", "exp": 1.0}
    token = await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    assert await account_deletion_service.verify_account_deletion_token(token) is None


# ---------------------------- send_deletion_email ----------------------------

@pytest.mark.asyncio
async def test_send_deletion_email_persists_single_use_token_in_valkey(mocker):
    mocker.patch(f"{MODULE}.account_deletion_service.create_account_deletion_token", return_value="delete-token-abc")
    mocker.patch(f"{MODULE}.send_email_task.defer_async", new_callable=AsyncMock)
    set_mock = mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock)

    result = await account_deletion_service.send_deletion_email(_FakeUser(), db=None)

    assert result is True
    set_mock.assert_awaited_once()
    args, kwargs = set_mock.call_args
    assert args[0] == "account_delete:delete-token-abc"
    assert kwargs["ex"] > 0


# ---------------------------- confirm_deletion ----------------------------

@pytest.mark.asyncio
async def test_confirm_deletion_succeeds_and_consumes_token(mocker):
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "user@example.com"},
    )
    getdel_mock = mocker.patch(f"{MODULE}.valkey_client.getdel", new_callable=AsyncMock, return_value="1")
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    finalize_mock = mocker.patch(f"{MODULE}.finalize_self_deletion", new_callable=AsyncMock)

    result = await account_deletion_service.confirm_deletion("valid-token", db=None)

    assert result is True
    getdel_mock.assert_awaited_once_with("account_delete:valid-token")
    finalize_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_deletion_rejects_replayed_or_unknown_token(mocker):
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.valkey_client.getdel", new_callable=AsyncMock, return_value=None)
    finalize_mock = mocker.patch(f"{MODULE}.finalize_self_deletion", new_callable=AsyncMock)

    result = await account_deletion_service.confirm_deletion("replayed-token", db=None)

    assert result is False
    finalize_mock.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_deletion_concurrent_replay_only_lets_one_request_through(mocker):
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.valkey_client.getdel", new_callable=AsyncMock, side_effect=["1", None])
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.finalize_self_deletion", new_callable=AsyncMock)

    first_result = await account_deletion_service.confirm_deletion("valid-token", db=None)
    second_result = await account_deletion_service.confirm_deletion("valid-token", db=None)

    assert first_result is True
    assert second_result is False


@pytest.mark.asyncio
async def test_confirm_deletion_rejects_invalid_jwt_before_touching_valkey(mocker):
    mocker.patch(f"{MODULE}.account_deletion_service.verify_account_deletion_token", return_value=None)
    getdel_mock = mocker.patch(f"{MODULE}.valkey_client.getdel", new_callable=AsyncMock)

    result = await account_deletion_service.confirm_deletion("garbage-token", db=None)

    assert result is False
    getdel_mock.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_deletion_rejects_unknown_user(mocker):
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "nobody@example.com"},
    )
    mocker.patch(f"{MODULE}.valkey_client.getdel", new_callable=AsyncMock, return_value="1")
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=None)
    finalize_mock = mocker.patch(f"{MODULE}.finalize_self_deletion", new_callable=AsyncMock)

    result = await account_deletion_service.confirm_deletion("valid-token", db=None)

    assert result is False
    finalize_mock.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_deletion_only_ever_finalizes_the_token_owning_account(mocker):
    # A token minted for account A's email always resolves to account A: the
    # email comes from the token's own signed payload, never from whoever
    # happens to call the confirm endpoint, so it's not possible for one
    # account's token to end up deleting a different account.
    mocker.patch(
        f"{MODULE}.account_deletion_service.verify_account_deletion_token",
        return_value={"email": "victim@example.com"},
    )
    mocker.patch(f"{MODULE}.valkey_client.getdel", new_callable=AsyncMock, return_value="1")
    get_by_email_mock = mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser("victim@example.com"))
    finalize_mock = mocker.patch(f"{MODULE}.finalize_self_deletion", new_callable=AsyncMock)

    await account_deletion_service.confirm_deletion("victims-token", db=None)

    get_by_email_mock.assert_awaited_once_with("victim@example.com", None)
    finalized_user = finalize_mock.call_args.args[0]
    assert finalized_user.email == "victim@example.com"
