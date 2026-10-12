# tests/backend/mystic_auth/unit/user/test_user_base_crud_joins_and_crud_unit.py
#
# UserBaseCRUD's policy/permission join-based filters (_apply_filters) plus
# update/delete. Column-level filter/sort builders and get_all/count's basic
# path live in test_user_base_crud_filters_unit.py - split out of one
# 354-line file, see AGENTS.md's ~350-line target.
#
# "policy" and "permission" aren't columns on the users table at all:
# matching them requires joining through user_policies -> policies, which is
# easy to get subtly wrong (missing distinct() double-counting a user who
# holds several matching policies, or leaking the join into every other,
# unrelated query). Covered directly against the compiled SQL, same approach
# as the column-level filters, rather than only indirectly via the
# route-level integration tests.
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from backend.mystic_auth.user.user_crud_modules.user_base_crud import UserBaseCRUD
from backend.mystic_auth.user.user_model import User as _FakeModel
from backend.mystic_auth.user.user_model import UserRole

# Real mapped model: select(...)/where(...)/order_by(...) require an actual
# ORM-mapped class or column expression, not a plain stand-in class.


def _make_db(scalar_return=None, scalars_all_return=None):
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=scalar_return)
    execute_result.scalar_one = MagicMock(return_value=scalar_return)
    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=scalars_all_return or [])
    execute_result.scalars = MagicMock(return_value=scalars_result)
    db.execute = AsyncMock(return_value=execute_result)
    return db


def test_apply_filters_without_policy_or_permission_does_not_join():
    crud = UserBaseCRUD(_FakeModel)

    stmt = crud._apply_filters(select(_FakeModel), None, None, None, None)

    compiled = str(stmt)
    assert "JOIN" not in compiled.upper()


def test_apply_filters_by_policy_name_joins_and_matches_on_policy_name():
    crud = UserBaseCRUD(_FakeModel)

    stmt = crud._apply_filters(select(_FakeModel), None, None, None, None, policy="user_management")

    compiled = str(stmt)
    assert "JOIN user_policies" in compiled
    assert "JOIN policies" in compiled
    assert "policies.name" in compiled
    # distinct() guards against a user matching via more than one policy row.
    assert "DISTINCT" in compiled.upper()


def test_apply_filters_by_permission_alone_matches_via_policy_or_direct_grant():
    """No `policy` filter alongside it: a user can hold this action either
    via a policy (Policy.actions contains it) or as a direct UserPermission
    grant that bypasses Policy entirely - both must match, or a user granted
    the permission directly (never through any policy) would be silently
    omitted from the filtered/counted results. Written as two EXISTS
    subqueries rather than a top-level join, so no distinct() is needed."""
    crud = UserBaseCRUD(_FakeModel)

    stmt = crud._apply_filters(select(_FakeModel), None, None, None, None, permission="users:list_all")

    compiled = str(stmt)
    assert "EXISTS" in compiled.upper()
    assert "JOIN policies" in compiled
    assert "policies.actions" in compiled
    assert "user_permissions" in compiled
    assert "user_permissions.action" in compiled
    assert "user_permissions.is_active" in compiled


def test_apply_filters_by_policy_and_permission_together_still_requires_both_on_the_same_assignment():
    """Unlike the permission-alone branch, `policy` + `permission` together
    keeps the original join-based semantics: the caller is asking for users
    whose *policy* assignment grants this specific action, not any direct
    grant - a direct UserPermission grant must not satisfy this combined
    filter."""
    crud = UserBaseCRUD(_FakeModel)

    stmt = crud._apply_filters(
        select(_FakeModel), None, None, None, None, policy="user_management", permission="users:list_all"
    )

    compiled = str(stmt)
    assert "JOIN user_policies" in compiled
    assert "JOIN policies" in compiled
    assert "policies.name" in compiled
    assert "policies.actions" in compiled
    assert "user_permissions" not in compiled
    assert "DISTINCT" in compiled.upper()


def test_verification_filter_excludes_deactivated_users_unless_status_is_explicit():
    crud = UserBaseCRUD(_FakeModel)

    verified = str(crud._apply_filters(select(_FakeModel), None, None, True, None))
    verified_deleted = str(crud._apply_filters(select(_FakeModel), None, None, True, "deleted"))

    assert "users.is_verified" in verified
    assert "users.is_active" in verified
    assert "users.deleted_at" in verified
    assert "users.is_verified" in verified_deleted
    assert "users.deleted_at" in verified_deleted


def test_apply_filters_keeps_all_user_filters_conjunctive():
    """A policy/permission join must not loosen the ordinary user filters.

    This is the regression shape behind combinations such as verified + policy
    (and the same applies to role/status/search/last-login). The generated
    statement must retain every predicate when relationship filters are added.
    """
    crud = UserBaseCRUD(_FakeModel)

    stmt = crud._apply_filters(
        select(_FakeModel),
        "matrix",
        UserRole.user,
        True,
        "active",
        policy="user_management",
        permission="users:list_all",
        permission_source="policy",
        last_login="30d",
    )

    compiled = str(stmt)
    assert "users.name" in compiled
    assert "users.role" in compiled
    assert "users.is_verified" in compiled
    assert "users.is_active" in compiled
    assert "users.deleted_at" in compiled
    assert "users.last_login_at" in compiled
    assert "policies.name" in compiled
    assert "policies.actions" in compiled


@pytest.mark.asyncio
async def test_get_all_threads_policy_and_permission_through_to_apply_filters():
    db = _make_db(scalars_all_return=["row1"])
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.get_all(db, policy="user_management", permission="users:list_all")

    assert result == ["row1"]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_threads_policy_and_permission_through_to_apply_filters():
    db = _make_db(scalar_return=3)
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.count(db, policy="user_management", permission="users:list_all")

    assert result == 3


@pytest.mark.asyncio
async def test_update_applies_every_field_and_persists():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db_obj = _FakeModel()
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.update(db_obj, {"name": "Updated Name"}, db)

    assert result.name == "Updated Name"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_returns_none_when_there_is_no_target_row():
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.update(None, {"name": "Doesn't matter"}, AsyncMock())

    assert result is None


@pytest.mark.asyncio
async def test_delete_removes_the_row_and_returns_true():
    db = AsyncMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.delete(_FakeModel(), db)

    assert result is True
    db.delete.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_returns_false_when_there_is_no_target_row():
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.delete(None, AsyncMock())

    assert result is False
