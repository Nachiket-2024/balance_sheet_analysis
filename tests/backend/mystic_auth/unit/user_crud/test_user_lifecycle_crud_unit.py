# tests/backend/mystic_auth/unit/user_crud/test_user_lifecycle_crud_unit.py
#
# UserLifecycleCRUD backs the soft-delete/reactivate flow every other
# safety check (login, current-user, purge eligibility) ultimately depends
# on; deliberately kept separate from UserBaseCRUD.update (see its own
# docstring) since these two columns are app-computed, never caller-supplied.
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.user_crud.user_crud_modules.user_lifecycle_crud import UserLifecycleCRUD
from backend.mystic_auth.user_table.user_model import User as _FakeModel


@pytest.mark.asyncio
async def test_soft_delete_sets_inactive_and_stamps_deleted_at():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db_obj = _FakeModel(is_active=True, deleted_at=None)
    crud = UserLifecycleCRUD(_FakeModel)

    before = datetime.now(UTC)
    result = await crud.soft_delete(db_obj, db)
    after = datetime.now(UTC)

    assert result.is_active is False
    assert before <= result.deleted_at <= after
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_soft_delete_returns_none_when_there_is_no_target_row():
    crud = UserLifecycleCRUD(_FakeModel)

    result = await crud.soft_delete(None, AsyncMock())

    assert result is None


@pytest.mark.asyncio
async def test_reactivate_sets_active_and_clears_deleted_at():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db_obj = _FakeModel(is_active=False, deleted_at=datetime.now(UTC))
    crud = UserLifecycleCRUD(_FakeModel)

    result = await crud.reactivate(db_obj, db)

    assert result.is_active is True
    assert result.deleted_at is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reactivate_returns_none_when_there_is_no_target_row():
    crud = UserLifecycleCRUD(_FakeModel)

    result = await crud.reactivate(None, AsyncMock())

    assert result is None
