# tests/backend/mystic_auth/unit/test_account_verification_service_unit.py
#
# Regression guard for a Phase 1 auth-audit fix to verify_token:
#   Single-use enforcement previously did a separate GET then DELETE against
#   Redis, a TOCTOU race let two concurrent requests both pass the GET
#   before either ran the DELETE, both treating a single-use token as valid.
#   Fixed by using an atomic GETDEL.
#
# Token-purpose scoping (this token must never work anywhere else) is
# enforced by jwt_service.verify_token via expected_type="verify", see
# test_account_verification_requires_verify_type in test_jwt_unit.py,
# rather than by anything in this file.
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)

MODULE = "backend.mystic_auth.auth.verify_account.account_verification_service"


@pytest.mark.asyncio
async def test_verify_token_uses_atomic_getdel_not_separate_get_and_delete(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "verify"},
    )
    getdel_mock = mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value="1")
    get_mock = mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock)
    delete_mock = mocker.patch(f"{MODULE}.redis_client.delete", new_callable=AsyncMock)

    result = await account_verification_service.verify_token("some-token")

    assert result == {"email": "user@example.com", "type": "verify"}
    getdel_mock.assert_awaited_once_with("verify:some-token")
    # No separate GET/DELETE round-trip: the whole point of the fix is that
    # a single atomic operation replaces the racy two-step check.
    get_mock.assert_not_called()
    delete_mock.assert_not_called()


@pytest.mark.asyncio
async def test_verify_token_rejects_already_consumed_single_use_token(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "verify"},
    )
    mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock, return_value=None)

    result = await account_verification_service.verify_token("already-used-token")

    assert result is None


@pytest.mark.asyncio
async def test_create_verification_token_forwards_expires_minutes_to_jwt_service(mocker):
    """Regression guard: create_verification_token used to call
    jwt_service.create_verification_token(email=email) without forwarding
    expires_minutes, so the JWT's own exp claim silently used
    ACCESS_TOKEN_EXPIRE_MINUTES (15min default) while the Redis single-use
    key TTL and the emailed wording both used RESET_TOKEN_EXPIRE_MINUTES
    (60min default), so a user clicking between 15-60 minutes in got a
    confusing invalid/expired error despite the email promising the link
    should still work."""
    create_mock = mocker.patch(
        f"{MODULE}.jwt_service.create_verification_token", new_callable=AsyncMock, return_value="token"
    )

    await account_verification_service.create_verification_token("user@example.com", expires_minutes=45)

    create_mock.assert_awaited_once_with(email="user@example.com", expires_minutes=45)


@pytest.mark.asyncio
async def test_verify_token_rejects_token_of_the_wrong_type(mocker):
    # A validly-signed, unexpired token minted for some other purpose (not
    # type="verify") must never be accepted here. jwt_service.verify_token
    # itself enforces expected_type, so it returns None before this service
    # ever sees a payload.
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value=None,
    )
    getdel_mock = mocker.patch(f"{MODULE}.redis_client.getdel", new_callable=AsyncMock)

    result = await account_verification_service.verify_token("wrong-type-token")

    assert result is None
    getdel_mock.assert_not_called()


@pytest.mark.asyncio
async def test_send_verification_email_if_needed_sends_for_unverified_user(mocker):
    user = SimpleNamespace(is_verified=False)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=user)
    send_mock = mocker.patch(
        f"{MODULE}.AccountVerificationService.send_verification_email",
        new_callable=AsyncMock,
        return_value=True,
    )

    result = await account_verification_service.send_verification_email_if_needed("user@example.com", db=None)

    assert result is True
    send_mock.assert_awaited_once_with("user@example.com")


@pytest.mark.asyncio
async def test_send_verification_email_if_needed_skips_unknown_email(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=None)
    send_mock = mocker.patch(
        f"{MODULE}.AccountVerificationService.send_verification_email",
        new_callable=AsyncMock,
    )

    result = await account_verification_service.send_verification_email_if_needed("missing@example.com", db=None)

    assert result is False
    send_mock.assert_not_called()


@pytest.mark.asyncio
async def test_send_verification_email_if_needed_skips_already_verified_user(mocker):
    user = SimpleNamespace(is_verified=True)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=user)
    send_mock = mocker.patch(
        f"{MODULE}.AccountVerificationService.send_verification_email",
        new_callable=AsyncMock,
    )

    result = await account_verification_service.send_verification_email_if_needed("user@example.com", db=None)

    assert result is False
    send_mock.assert_not_called()
