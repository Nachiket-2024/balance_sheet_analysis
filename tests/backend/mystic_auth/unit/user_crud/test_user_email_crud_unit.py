# tests/backend/mystic_auth/unit/test_user_email_crud_unit.py
#
# Regression guard for email-casing normalization: `User@Example.com` and
# `user@example.com` must resolve to the same account. UserEmailCRUD is the
# single choke point every lookup in the app goes through (login,
# current-user, admin routes, OAuth2), so normalizing here, rather than
# trusting every caller to normalize first, is what makes casing
# consistent everywhere without touching each call site.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.user_crud.user_crud_modules.user_base_crud import UserBaseCRUD
from backend.mystic_auth.user_crud.user_crud_modules.user_email_crud import (
    UserEmailCRUD,
)

# Real mapped model: select(...)/where(...) require an actual ORM-mapped
# class or column expression, not a plain stand-in class.
from backend.mystic_auth.user_table.user_model import User as _FakeModel

EMAIL_CRUD_MODULE = "backend.mystic_auth.user_crud.user_crud_modules.user_email_crud"
BASE_CRUD_MODULE = "backend.mystic_auth.user_crud.user_crud_modules.user_base_crud"


def _make_db(scalar_return=None):
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=scalar_return)
    db.execute = AsyncMock(return_value=execute_result)
    return db


@pytest.mark.asyncio
async def test_get_by_email_normalizes_casing_before_querying(mocker):
    normalize_mock = mocker.patch(f"{EMAIL_CRUD_MODULE}.normalize_email", return_value="user@example.com")
    db = _make_db()
    crud = UserEmailCRUD(_FakeModel)

    await crud.get_by_email("User@Example.com", db)

    normalize_mock.assert_called_once_with("User@Example.com")
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_email_finds_account_regardless_of_input_casing():
    # No mocking of normalize_email here: exercises the real function so a
    # regression in its lowercase/strip logic would actually be caught.
    db = _make_db(scalar_return="fake-user-row")
    crud = UserEmailCRUD(_FakeModel)

    result = await crud.get_by_email("  USER@EXAMPLE.COM  ", db)

    assert result == "fake-user-row"


@pytest.mark.asyncio
async def test_update_by_email_normalizes_via_get_by_email(mocker):
    # update_by_email delegates to get_by_email, so normalization only needs
    # to happen once, this guards against that delegation ever changing to
    # bypass get_by_email and losing normalization.
    normalize_mock = mocker.patch(f"{EMAIL_CRUD_MODULE}.normalize_email", return_value="user@example.com")
    db = _make_db(scalar_return=None)
    crud = UserEmailCRUD(_FakeModel)

    result = await crud.update_by_email("User@Example.com", {"name": "New Name"}, db)

    normalize_mock.assert_called_once_with("User@Example.com")
    assert result is None


@pytest.mark.asyncio
async def test_create_normalizes_email_before_storing(mocker):
    normalize_mock = mocker.patch(f"{BASE_CRUD_MODULE}.normalize_email", return_value="user@example.com")
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    crud = UserBaseCRUD(_FakeModel)

    obj = await crud.create({"email": "User@Example.com", "name": "Test"}, db)

    normalize_mock.assert_called_once_with("User@Example.com")
    assert obj.email == "user@example.com"


@pytest.mark.asyncio
async def test_create_does_not_require_an_email_field():
    # create() is generic, not every obj_data dict necessarily carries an
    # "email" key, must not raise a KeyError when it's absent.
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    crud = UserBaseCRUD(_FakeModel)

    obj = await crud.create({"name": "No Email Field"}, db)

    assert obj.name == "No Email Field"
