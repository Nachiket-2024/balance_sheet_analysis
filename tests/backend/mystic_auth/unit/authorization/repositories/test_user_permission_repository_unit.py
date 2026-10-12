# Coverage for UserPermissionRepository's cache-aside wiring, the
# insert-vs-reactivate-existing-row branch in assign_permission_to_user, and the
# bulk stage-then-commit-once/per-user-invalidation contract (shared with
# PolicyAssignmentRepository; see test_policy_repository_caching_unit.py).
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.authorization.repositories.user_permission_repository import (
    UserPermissionRepository,
)
from backend.mystic_auth.authorization.schemas.bulk_schema import (
    BulkPermissionItem,
    BulkPermissionRemoveItem,
)

REPO_MODULE = "backend.mystic_auth.authorization.repositories.user_permission_repository"


def _make_user(user_id=1, email="user@example.com"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    return user


def _make_grant(**overrides):
    grant = MagicMock()
    grant.user_id = 1
    grant.action = "users:read_own"
    grant.resource_type = "users"
    grant.conditions = None
    grant.is_active = True
    grant.assigned_by = None
    for key, value in overrides.items():
        setattr(grant, key, value)
    return grant


def _mock_cache(mocker, get_return=None):
    cache = MagicMock(
        get_user_permissions=AsyncMock(return_value=get_return),
        set_user_permissions=AsyncMock(),
        invalidate_user_permissions=AsyncMock(),
        invalidate_user_permissions_bulk=AsyncMock(),
    )
    mocker.patch(f"{REPO_MODULE}.authorization_cache_service", new=cache)
    return cache


# ---------------------------- get_active_permissions_for_user ----------------------------

@pytest.mark.asyncio
async def test_get_active_permissions_for_user_returns_cached_result_without_querying_db(mocker):
    cached_grants = [_make_grant()]
    cache = _mock_cache(mocker, get_return=cached_grants)
    db = MagicMock()
    db.execute = AsyncMock()

    result = await UserPermissionRepository.get_active_permissions_for_user("user@example.com", db)

    assert result is cached_grants
    db.execute.assert_not_called()
    cache.set_user_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_get_active_permissions_for_user_queries_db_and_populates_cache_on_miss(mocker):
    cache = _mock_cache(mocker, get_return=None)
    fetched_grants = [_make_grant()]
    scalars_result = MagicMock()
    scalars_result.all.return_value = fetched_grants
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db = MagicMock()
    db.execute = AsyncMock(return_value=execute_result)

    result = await UserPermissionRepository.get_active_permissions_for_user("user@example.com", db)

    assert result == fetched_grants
    db.execute.assert_awaited_once()
    cache.set_user_permissions.assert_awaited_once_with("user@example.com", fetched_grants)


# ---------------------------- assign_permission_to_user ----------------------------

@pytest.mark.asyncio
async def test_assign_permission_to_user_inserts_new_row_when_none_exists(mocker):
    cache = _mock_cache(mocker)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    await UserPermissionRepository.assign_permission_to_user(
        user_id=1, action="users:list_all", resource_type="users", conditions=None,
        db=db, assigned_by="admin@example.com", user_email="target@example.com",
    )

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.user_id == 1
    assert added.action == "users:list_all"
    db.commit.assert_awaited_once()
    cache.invalidate_user_permissions.assert_awaited_once_with("target@example.com")


@pytest.mark.asyncio
async def test_assign_permission_to_user_reactivates_and_updates_existing_row_on_conflict(mocker):
    """Unlike PolicyAssignmentRepository.assign_policy_to_user, re-assigning
    an already-held (action, resource_type) is not a pure no-op: it updates
    `conditions`/`assigned_by` in place and flips `is_active` back on."""
    cache = _mock_cache(mocker)
    existing_row = _make_grant(is_active=False, conditions=None, assigned_by="old-admin@example.com")
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_row)))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    new_conditions = {"tenant_id": "abc"}
    result = await UserPermissionRepository.assign_permission_to_user(
        user_id=1, action="users:read_own", resource_type="users", conditions=new_conditions,
        db=db, assigned_by="admin@example.com", user_email="target@example.com",
    )

    assert result is existing_row
    assert existing_row.conditions == new_conditions
    assert existing_row.is_active is True
    assert existing_row.assigned_by == "admin@example.com"
    db.add.assert_called_once_with(existing_row)
    cache.invalidate_user_permissions.assert_awaited_once_with("target@example.com")


@pytest.mark.asyncio
async def test_assign_permission_to_user_skips_invalidation_when_email_not_given(mocker):
    cache = _mock_cache(mocker)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    await UserPermissionRepository.assign_permission_to_user(
        user_id=1, action="users:list_all", resource_type="users", conditions=None, db=db, assigned_by="system",
    )

    cache.invalidate_user_permissions.assert_not_called()


# ---------------------------- remove_permission_from_user ----------------------------

@pytest.mark.asyncio
async def test_remove_permission_from_user_deletes_and_invalidates_cache(mocker):
    cache = _mock_cache(mocker)
    existing_grant = _make_grant()
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_grant)))
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    removed = await UserPermissionRepository.remove_permission_from_user(
        user_id=1, action="users:read_own", resource_type="users", db=db, user_email="target@example.com",
    )

    assert removed is True
    db.delete.assert_awaited_once_with(existing_grant)
    cache.invalidate_user_permissions.assert_awaited_once_with("target@example.com")


@pytest.mark.asyncio
async def test_remove_permission_from_user_returns_false_when_not_held(mocker):
    cache = _mock_cache(mocker)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    removed = await UserPermissionRepository.remove_permission_from_user(
        user_id=1, action="users:read_own", resource_type="users", db=db, user_email="target@example.com",
    )

    assert removed is False
    db.delete.assert_not_called()
    cache.invalidate_user_permissions.assert_not_called()


# ---------------------------- bulk_assign_permissions ----------------------------

@pytest.mark.asyncio
async def test_bulk_assign_permissions_commits_once_and_invalidates_each_affected_user(mocker):
    cache = _mock_cache(mocker)
    user_a = _make_user(1, "a@example.com")
    user_b = _make_user(2, "b@example.com")
    valid_items = [
        (user_a, BulkPermissionItem(user_email="a@example.com", action="users:list_all", resource_type="users")),
        (user_b, BulkPermissionItem(user_email="b@example.com", action="users:list_all", resource_type="users")),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    db.add = MagicMock()
    db.commit = AsyncMock()

    results = await UserPermissionRepository.bulk_assign_permissions(valid_items, db, assigned_by="admin@example.com")

    assert len(results) == 2
    assert all(r.status == "success" for r in results)
    assert db.add.call_count == 2
    db.commit.assert_awaited_once()
    # Batched invalidation (one delete(*keys) call for every affected user),
    # not one invalidate_user_permissions round trip per user.
    cache.invalidate_user_permissions.assert_not_called()
    cache.invalidate_user_permissions_bulk.assert_awaited_once()
    invalidated = cache.invalidate_user_permissions_bulk.await_args.args[0]
    assert invalidated == {"a@example.com", "b@example.com"}


@pytest.mark.asyncio
async def test_bulk_assign_permissions_updates_existing_row_instead_of_duplicating(mocker):
    _mock_cache(mocker)
    user_a = _make_user(1, "a@example.com")
    existing_row = _make_grant(user_id=1, action="users:list_all", resource_type="users", is_active=False)
    valid_items = [
        (user_a, BulkPermissionItem(user_email="a@example.com", action="users:list_all", resource_type="users", conditions={"x": 1})),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[existing_row])))))
    db.add = MagicMock()
    db.commit = AsyncMock()

    results = await UserPermissionRepository.bulk_assign_permissions(valid_items, db, assigned_by="admin@example.com")

    assert results[0].status == "success"
    assert existing_row.is_active is True
    assert existing_row.conditions == {"x": 1}
    db.add.assert_called_once_with(existing_row)


@pytest.mark.asyncio
async def test_bulk_assign_permissions_returns_commit_failed_for_every_item_on_db_error(mocker):
    cache = _mock_cache(mocker)
    user_a = _make_user(1, "a@example.com")
    valid_items = [
        (user_a, BulkPermissionItem(user_email="a@example.com", action="users:list_all", resource_type="users")),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=RuntimeError("db exploded"))
    db.rollback = AsyncMock()

    results = await UserPermissionRepository.bulk_assign_permissions(valid_items, db, assigned_by="admin@example.com")

    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].error == "commit_failed"
    db.rollback.assert_awaited_once()
    cache.invalidate_user_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_assign_permissions_returns_empty_list_for_no_valid_items(mocker):
    _mock_cache(mocker)
    db = MagicMock()
    db.execute = AsyncMock()

    results = await UserPermissionRepository.bulk_assign_permissions([], db, assigned_by="admin@example.com")

    assert results == []
    db.execute.assert_not_called()


# ---------------------------- bulk_remove_permissions ----------------------------

@pytest.mark.asyncio
async def test_bulk_remove_permissions_deletes_held_grants_and_reports_not_held(mocker):
    cache = _mock_cache(mocker)
    user_a = _make_user(1, "a@example.com")
    user_b = _make_user(2, "b@example.com")
    held_row = _make_grant(user_id=1, action="users:list_all", resource_type="users")
    valid_items = [
        (user_a, BulkPermissionRemoveItem(user_email="a@example.com", action="users:list_all", resource_type="users")),
        (user_b, BulkPermissionRemoveItem(user_email="b@example.com", action="users:list_all", resource_type="users")),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[held_row])))))
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    results = await UserPermissionRepository.bulk_remove_permissions(valid_items, db)

    by_email = {r.user_email: r for r in results}
    assert by_email["a@example.com"].status == "success"
    assert by_email["b@example.com"].status == "error"
    assert by_email["b@example.com"].error == "not_held"
    db.delete.assert_awaited_once_with(held_row)
    # Batched invalidation, see the equivalent bulk_assign_permissions test.
    cache.invalidate_user_permissions.assert_not_called()
    cache.invalidate_user_permissions_bulk.assert_awaited_once_with({"a@example.com"})


@pytest.mark.asyncio
async def test_bulk_remove_permissions_preserves_not_held_errors_on_commit_failure(mocker):
    """A commit failure should only downgrade the items that actually
    staged a delete (status == 'success') to 'commit_failed' - an item
    already reported as 'not_held' before the commit was ever attempted
    must keep its original error."""
    cache = _mock_cache(mocker)
    user_a = _make_user(1, "a@example.com")
    user_b = _make_user(2, "b@example.com")
    held_row = _make_grant(user_id=1, action="users:list_all", resource_type="users")
    valid_items = [
        (user_a, BulkPermissionRemoveItem(user_email="a@example.com", action="users:list_all", resource_type="users")),
        (user_b, BulkPermissionRemoveItem(user_email="b@example.com", action="users:list_all", resource_type="users")),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[held_row])))))
    db.delete = AsyncMock()
    db.commit = AsyncMock(side_effect=RuntimeError("db exploded"))
    db.rollback = AsyncMock()

    results = await UserPermissionRepository.bulk_remove_permissions(valid_items, db)

    by_email = {r.user_email: r for r in results}
    assert by_email["a@example.com"].status == "error"
    assert by_email["a@example.com"].error == "commit_failed"
    assert by_email["b@example.com"].status == "error"
    assert by_email["b@example.com"].error == "not_held"
    cache.invalidate_user_permissions.assert_not_called()
