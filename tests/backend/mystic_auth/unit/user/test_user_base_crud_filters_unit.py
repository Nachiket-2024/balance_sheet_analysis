# tests/backend/mystic_auth/unit/user/test_user_base_crud_filters_unit.py
#
# UserBaseCRUD's column-level filter/sort builders (_search_filter,
# _status_filter, _last_login_filter, _order_by) plus get_all/count's basic
# no-relationship-filter path. Its policy/permission join-based filters and
# CRUD (update/delete) live in test_user_base_crud_joins_and_crud_unit.py -
# split out of one 354-line file, see AGENTS.md's ~350-line target.
#
# Its filter/sort-column allowlisting is the one thing standing between a
# caller-supplied query param and an arbitrary SQL column reference, so it's
# exercised directly here rather than only indirectly through the
# route-level integration tests.
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.user.user_crud_modules.user_base_crud import UserBaseCRUD
from backend.mystic_auth.user.user_model import User as _FakeModel

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


@pytest.mark.asyncio
async def test_get_by_id_returns_the_matching_row():
    db = _make_db(scalar_return="fake-user-row")
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.get_by_id(1, db)

    assert result == "fake-user-row"
    db.execute.assert_awaited_once()


def test_search_filter_is_none_for_empty_or_missing_search():
    crud = UserBaseCRUD(_FakeModel)

    assert crud._search_filter(None) is None
    assert crud._search_filter("") is None


def test_search_filter_matches_name_or_email_case_insensitively():
    crud = UserBaseCRUD(_FakeModel)

    condition = crud._search_filter("someone")

    compiled = str(condition)
    assert "lower" in compiled  # ilike compiles to a case-insensitive comparison
    assert "name" in compiled
    assert "email" in compiled


@pytest.mark.parametrize(
    ("status", "expect_is_active", "expect_deleted_at_none"),
    [
        ("active", True, True),
        ("inactive", False, True),
    ],
)
def test_status_filter_active_and_inactive_exclude_deleted_rows(status, expect_is_active, expect_deleted_at_none):
    crud = UserBaseCRUD(_FakeModel)

    condition = crud._status_filter(status)

    compiled = str(condition)
    assert "is_active" in compiled
    assert "deleted_at" in compiled


def test_status_filter_deleted_only_checks_deleted_at():
    crud = UserBaseCRUD(_FakeModel)

    condition = crud._status_filter("deleted")

    compiled = str(condition)
    assert "deleted_at" in compiled
    assert "is_active" not in compiled


def test_status_filter_is_none_when_no_status_given():
    crud = UserBaseCRUD(_FakeModel)

    assert crud._status_filter(None) is None


@pytest.mark.parametrize(
    ("bucket", "expected_sql"),
    [
        ("never", "last_login_at IS NULL"),
        ("today", "last_login_at IS NOT NULL"),
        ("7d", "last_login_at IS NOT NULL"),
        ("30d", "last_login_at IS NOT NULL"),
        ("90d", "last_login_at IS NOT NULL"),
    ],
)
def test_last_login_bucket_filter_covers_every_supported_bucket(bucket, expected_sql):
    crud = UserBaseCRUD(_FakeModel)

    condition = crud._last_login_filter(bucket, None, None)

    assert condition is not None
    assert expected_sql in str(condition)


def test_last_login_open_ended_custom_range_is_conjunctive():
    crud = UserBaseCRUD(_FakeModel)
    lower = datetime(2026, 1, 1, tzinfo=UTC)
    upper = datetime(2026, 2, 1, tzinfo=UTC)

    condition = crud._last_login_filter(None, lower, upper)

    compiled = str(condition)
    assert "last_login_at IS NOT NULL" in compiled
    assert "last_login_at >=" in compiled
    assert "last_login_at <=" in compiled


def test_order_by_falls_back_to_id_for_a_disallowed_sort_column():
    # "status" is a UI-level composite of two real columns, deliberately not
    # in the sortable allowlist; an unrecognized sort_by must never reach
    # getattr(self.model, sort_by) unguarded.
    crud = UserBaseCRUD(_FakeModel)

    clauses = crud._order_by("status", "asc")

    compiled = [str(c) for c in clauses]
    assert all("status" not in c for c in compiled)
    assert any("id" in c for c in compiled)


def test_order_by_uses_the_requested_allowlisted_column_and_direction():
    crud = UserBaseCRUD(_FakeModel)

    clauses = crud._order_by("email", "desc")

    compiled = [str(c) for c in clauses]
    assert any("email" in c and "DESC" in c for c in compiled)
    # id is always the secondary sort key, for stable ordering.
    assert any("id" in c and "DESC" in c for c in compiled)


@pytest.mark.asyncio
async def test_get_all_returns_the_rows_from_the_query():
    db = _make_db(scalars_all_return=["row1", "row2"])
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.get_all(db)

    assert result == ["row1", "row2"]


@pytest.mark.asyncio
async def test_count_returns_the_scalar_total():
    db = _make_db(scalar_return=42)
    crud = UserBaseCRUD(_FakeModel)

    result = await crud.count(db)

    assert result == 42
