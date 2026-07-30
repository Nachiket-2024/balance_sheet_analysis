# tests/backend/mystic_auth/unit/test_create_system_user_unit.py
#
# Covers the promotion path added to create_system_user.py: running the
# script against an email that already belongs to an existing account (e.g.
# someone who signed up/logged in via Google before ever bootstrapping the
# system user) should offer to promote that account instead of hard-refusing
# : but branches on whether that account has a password at all:
#   - has a password: promote in place (assign baseline policies, set
#     role=system, require a new password), after confirmation.
#   - no password (Google-only): can't be promoted as-is (no login method
#     would remain once Google login is disabled for it) : offer to delete
#     and recreate fresh instead, after confirmation.
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.scripts.create_system_user import (
    SYSTEM_ROLE,
    SYSTEM_USER_POLICY_NAMES,
    create_system_user,
)

MODULE = "backend.mystic_auth.scripts.create_system_user"


def _fake_policy(name):
    return SimpleNamespace(id=hash(name) % 1000, name=name)


def _existing_user(**overrides):
    defaults = dict(
        id=42,
        email="existing@example.com",
        name="Existing User",
        role=SimpleNamespace(value="user"),
        hashed_password="already-hashed",
    )
    return SimpleNamespace(**{**defaults, **overrides})


def _patch_db_session(mocker):
    """`create_system_user` does `async for db in database.get_session()`
    : a real async generator yielding one throwaway session object is enough
    for these tests, none of which care about the object's own identity."""

    async def _fake_get_session():
        yield object()

    mocker.patch(f"{MODULE}.database.get_session", side_effect=_fake_get_session)


def _patch_policies(mocker, found=True):
    mocker.patch(
        f"{MODULE}.policy_repository.get_by_name",
        new_callable=AsyncMock,
        side_effect=(lambda name, db: _fake_policy(name)) if found else (lambda name, db: None),
    )
    return mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)


@pytest.mark.asyncio
async def test_creates_a_new_user_when_the_email_does_not_exist(mocker):
    _patch_db_session(mocker)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{MODULE}.password_service.hash_password", new_callable=AsyncMock, return_value="hashed")
    new_user = SimpleNamespace(id=1, email="new@example.com")
    create_mock = mocker.patch(f"{MODULE}.user_crud.create", new_callable=AsyncMock, return_value=new_user)
    assign_mock = _patch_policies(mocker)
    mocker.patch("builtins.input", side_effect=["new@example.com", "New User"])
    mocker.patch(f"{MODULE}.getpass.getpass", return_value="a-password")

    await create_system_user()

    create_mock.assert_awaited_once()
    assert assign_mock.await_count == len(SYSTEM_USER_POLICY_NAMES)
    for call in assign_mock.await_args_list:
        assert call.kwargs["user_id"] == 1


@pytest.mark.asyncio
async def test_promotes_an_existing_password_user_when_confirmed(mocker):
    _patch_db_session(mocker)
    existing = _existing_user()
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=existing)
    create_mock = mocker.patch(f"{MODULE}.user_crud.create", new_callable=AsyncMock)
    delete_mock = mocker.patch(f"{MODULE}.user_crud.delete", new_callable=AsyncMock)
    update_mock = mocker.patch(f"{MODULE}.user_crud.update", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.password_service.hash_password", new_callable=AsyncMock, return_value="new-hashed")
    assign_mock = _patch_policies(mocker)
    mocker.patch("builtins.input", side_effect=["existing@example.com", "y"])
    mocker.patch(f"{MODULE}.getpass.getpass", return_value="a-new-password")

    await create_system_user()

    # Promotion never creates a new row or deletes the existing one : only
    # assigns policies and updates role/password in place.
    create_mock.assert_not_called()
    delete_mock.assert_not_called()
    assert assign_mock.await_count == len(SYSTEM_USER_POLICY_NAMES)
    for call in assign_mock.await_args_list:
        assert call.kwargs["user_id"] == 42
        assert call.kwargs["user_email"] == "existing@example.com"
    update_mock.assert_awaited_once_with(existing, {"role": SYSTEM_ROLE, "hashed_password": "new-hashed"}, mocker.ANY)


@pytest.mark.asyncio
async def test_declines_promotion_of_a_password_user_when_not_confirmed(mocker):
    _patch_db_session(mocker)
    existing = _existing_user()
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=existing)
    create_mock = mocker.patch(f"{MODULE}.user_crud.create", new_callable=AsyncMock)
    update_mock = mocker.patch(f"{MODULE}.user_crud.update", new_callable=AsyncMock)
    assign_mock = mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    # Anything other than exactly "y" is a decline : including empty input
    # (just pressing Enter), matching the "[y/N]" prompt's own default.
    mocker.patch("builtins.input", side_effect=["existing@example.com", ""])

    await create_system_user()

    create_mock.assert_not_called()
    update_mock.assert_not_called()
    assign_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_promotion_stops_if_a_baseline_policy_is_missing(mocker):
    _patch_db_session(mocker)
    existing = _existing_user()
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=existing)
    update_mock = mocker.patch(f"{MODULE}.user_crud.update", new_callable=AsyncMock)
    # First baseline policy lookup returns None : migrations haven't run.
    assign_mock = _patch_policies(mocker, found=False)
    mocker.patch("builtins.input", side_effect=["existing@example.com", "y"])

    await create_system_user()

    assign_mock.assert_not_awaited()
    # Never gets as far as prompting for/setting a new password.
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_deletes_and_recreates_a_google_only_account_when_confirmed(mocker):
    _patch_db_session(mocker)
    google_only = _existing_user(hashed_password=None)
    # Second get_by_email call (inside the fresh-creation branch, after the
    # delete) would normally re-query : this script doesn't re-query, it
    # just clears `existing` locally, so get_by_email is only ever called once.
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=google_only)
    delete_mock = mocker.patch(f"{MODULE}.user_crud.delete", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.password_service.hash_password", new_callable=AsyncMock, return_value="hashed")
    new_user = SimpleNamespace(id=99, email="existing@example.com")
    create_mock = mocker.patch(f"{MODULE}.user_crud.create", new_callable=AsyncMock, return_value=new_user)
    assign_mock = _patch_policies(mocker)
    mocker.patch("builtins.input", side_effect=["existing@example.com", "y", "Fresh Name"])
    mocker.patch(f"{MODULE}.getpass.getpass", return_value="a-fresh-password")

    await create_system_user()

    delete_mock.assert_awaited_once_with(google_only, mocker.ANY)
    create_mock.assert_awaited_once()
    assert create_mock.await_args.args[0]["email"] == "existing@example.com"
    assert assign_mock.await_count == len(SYSTEM_USER_POLICY_NAMES)
    for call in assign_mock.await_args_list:
        assert call.kwargs["user_id"] == 99


@pytest.mark.asyncio
async def test_declines_deleting_a_google_only_account_when_not_confirmed(mocker):
    _patch_db_session(mocker)
    google_only = _existing_user(hashed_password=None)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=google_only)
    delete_mock = mocker.patch(f"{MODULE}.user_crud.delete", new_callable=AsyncMock)
    create_mock = mocker.patch(f"{MODULE}.user_crud.create", new_callable=AsyncMock)
    mocker.patch("builtins.input", side_effect=["existing@example.com", ""])

    await create_system_user()

    delete_mock.assert_not_called()
    create_mock.assert_not_called()
