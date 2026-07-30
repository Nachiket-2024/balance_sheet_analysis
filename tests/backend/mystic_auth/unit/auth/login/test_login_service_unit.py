# tests/backend/mystic_auth/unit/test_login_service_unit.py
#
# Regression guard for the login timing side-channel: login() previously
# returned immediately (skipping the Argon2 comparison) for "user not
# found" and "user unverified", but performed a real hash comparison for
# "wrong password on an existing, verified account" : an attacker could
# distinguish these cases purely by response latency, enabling account
# enumeration despite every branch already returning the same generic
# failure. The fix makes login() always perform exactly one comparison,
# against the user's real hash if one exists or a fixed dummy hash
# otherwise, before any not-found/unverified branching.
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.login.login_service import login_service
from backend.mystic_auth.auth.password_logic.password_service import password_service

MODULE = "backend.mystic_auth.auth.login.login_service"


class _FakeUser:
    def __init__(self, role_value="user", is_verified=True, is_active=True, hashed_password="real-hash"):
        class _Role:
            value = role_value
        self.role = _Role()
        self.is_verified = is_verified
        self.is_active = is_active
        self.hashed_password = hashed_password


@pytest.mark.asyncio
async def test_login_nonexistent_user_still_performs_a_hash_comparison(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=None)
    verify_mock = mocker.patch(
        f"{MODULE}.password_service.verify_password", new_callable=AsyncMock, return_value=False
    )

    result = await login_service.login(email="nobody@example.com", password="whatever", db=None)

    assert result is None
    # Must compare against the fixed dummy hash, never skip the comparison,
    # so this branch's timing matches a genuine wrong-password comparison.
    verify_mock.assert_awaited_once_with("whatever", password_service.DUMMY_HASH)


@pytest.mark.asyncio
async def test_login_unverified_user_still_performs_a_hash_comparison(mocker):
    user = _FakeUser(is_verified=False, hashed_password="real-hash-for-unverified-user")
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=user)
    verify_mock = mocker.patch(
        f"{MODULE}.password_service.verify_password", new_callable=AsyncMock, return_value=True
    )

    result = await login_service.login(email="unverified@example.com", password="whatever", db=None)

    assert result is None
    verify_mock.assert_awaited_once_with("whatever", "real-hash-for-unverified-user")


@pytest.mark.asyncio
async def test_login_oauth2_only_user_with_no_password_uses_dummy_hash(mocker):
    # is_verified=True (OAuth2 users are pre-verified) but hashed_password
    # is None : password login for such an account must still compare
    # against something rather than skip straight to "wrong password".
    user = _FakeUser(is_verified=True, hashed_password=None)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=user)
    verify_mock = mocker.patch(
        f"{MODULE}.password_service.verify_password", new_callable=AsyncMock, return_value=False
    )

    result = await login_service.login(email="oauth-only@example.com", password="whatever", db=None)

    assert result is None
    verify_mock.assert_awaited_once_with("whatever", password_service.DUMMY_HASH)


@pytest.mark.asyncio
async def test_login_wrong_password_on_verified_account_still_fails(mocker):
    user = _FakeUser(is_verified=True, hashed_password="real-hash")
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=user)
    mocker.patch(f"{MODULE}.password_service.verify_password", new_callable=AsyncMock, return_value=False)

    result = await login_service.login(email="user@example.com", password="wrong", db=None)

    assert result is None


@pytest.mark.asyncio
async def test_login_deactivated_account_is_blocked_even_with_correct_password(mocker):
    # A deactivated account must not receive tokens at all, even when the
    # password is correct : current_user_handler.py would reject the tokens
    # on first use anyway, but issuing them here is wasteful/misleading.
    user = _FakeUser(is_verified=True, is_active=False, hashed_password="real-hash")
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=user)
    mocker.patch(f"{MODULE}.password_service.verify_password", new_callable=AsyncMock, return_value=True)
    create_access_mock = mocker.patch(f"{MODULE}.jwt_service.create_access_token", new_callable=AsyncMock)

    result = await login_service.login(email="deactivated@example.com", password="correct", db=None)

    assert result is None
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_login_correct_password_on_verified_account_succeeds(mocker):
    user = _FakeUser(is_verified=True, hashed_password="real-hash")
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=user)
    mocker.patch(f"{MODULE}.password_service.verify_password", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", new_callable=AsyncMock, return_value="access")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", new_callable=AsyncMock, return_value="refresh")

    result = await login_service.login(email="user@example.com", password="correct", db=None)

    assert result is not None
    assert result.access_token == "access"
    assert result.refresh_token == "refresh"


@pytest.mark.asyncio
async def test_login_missing_credentials_returns_none_without_hash_comparison(mocker):
    verify_mock = mocker.patch(f"{MODULE}.password_service.verify_password", new_callable=AsyncMock)
    get_by_email_mock = mocker.patch(f"{MODULE}.user_crud.get_by_email")

    result = await login_service.login(email="", password="", db=None)

    assert result is None
    verify_mock.assert_not_called()
    get_by_email_mock.assert_not_called()


@pytest.mark.asyncio
async def test_dummy_hash_is_a_real_argon2_hash_not_a_placeholder_string():
    # The dummy hash must be a genuine hash so verify_password performs
    # real Argon2 work on it : a plain sentinel string would let the
    # verify call short-circuit before doing any actual hashing/comparison,
    # reopening the exact timing gap this fix closes.
    assert password_service.DUMMY_HASH.startswith("$argon2")
