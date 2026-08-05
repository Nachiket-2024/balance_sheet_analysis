# tests/backend/mystic_auth/unit/user_crud/test_user_role_crud_unit.py
#
# UserRoleCRUD backs the PATCH /users/{email}/role endpoint. Role is
# display/grouping metadata only under this app's PBAC model (see
# authorization/) - these tests confirm the CRUD layer itself just persists
# whatever role value it's given, with no authorization logic of its own;
# that decision lives entirely in user_management_routes.py's dependency.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.user_crud.user_crud_modules.user_role_crud import UserRoleCRUD
from backend.mystic_auth.user_table.user_model import User as _FakeModel
from backend.mystic_auth.user_table.user_model import UserRole


@pytest.mark.asyncio
async def test_get_by_role_returns_matching_rows():
    db = AsyncMock()
    execute_result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=["admin1", "admin2"])
    execute_result.scalars = MagicMock(return_value=scalars_result)
    db.execute = AsyncMock(return_value=execute_result)
    crud = UserRoleCRUD(_FakeModel)

    result = await crud.get_by_role(UserRole.admin, db)

    assert result == ["admin1", "admin2"]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_role_persists_the_new_role():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db_obj = _FakeModel(role=UserRole.user)
    crud = UserRoleCRUD(_FakeModel)

    result = await crud.update_role(db_obj, UserRole.admin, db)

    assert result.role == UserRole.admin
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_role_returns_none_when_there_is_no_target_row():
    crud = UserRoleCRUD(_FakeModel)

    result = await crud.update_role(None, UserRole.admin, AsyncMock())

    assert result is None
