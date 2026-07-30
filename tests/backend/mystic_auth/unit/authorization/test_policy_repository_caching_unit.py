# tests/backend/mystic_auth/unit/test_policy_repository_caching_unit.py
#
# Coverage for PolicyRepository's cache-aside wiring around
# get_active_policies_for_user, and the invalidation hooks in
# update/delete/assign/remove : claude.md's Authorization Performance
# Layer: "invalidation triggers: policy updates, deletion, assignment,
# revocation", "no stale data served".
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.authorization.repositories.policy_repository import PolicyRepository

REPO_MODULE = "backend.mystic_auth.authorization.repositories.policy_repository"


def _make_policy(**overrides):
    policy = MagicMock()
    policy.id = 1
    policy.name = "self_service"
    policy.description = "baseline"
    policy.actions = ["users:read_own"]
    policy.resource_type = "users"
    policy.conditions = None
    policy.is_active = True
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


def _mock_cache(mocker, get_return=None):
    cache = MagicMock(
        get_user_policies=AsyncMock(return_value=get_return),
        set_user_policies=AsyncMock(),
        invalidate_user_policies=AsyncMock(),
        invalidate_all_user_policies=AsyncMock(),
    )
    mocker.patch(f"{REPO_MODULE}.authorization_cache_service", new=cache)
    return cache


# ---------------------------- Cache hit skips the database ----------------------------

@pytest.mark.asyncio
async def test_get_active_policies_for_user_returns_cached_result_without_querying_db(mocker):
    cached_policies = [_make_policy()]
    cache = _mock_cache(mocker, get_return=cached_policies)
    db = MagicMock()
    db.execute = AsyncMock()

    result = await PolicyRepository.get_active_policies_for_user("user@example.com", db)

    assert result is cached_policies
    db.execute.assert_not_called()
    cache.set_user_policies.assert_not_called()


# ---------------------------- Cache miss queries DB and populates cache ----------------------------

@pytest.mark.asyncio
async def test_get_active_policies_for_user_queries_db_and_populates_cache_on_miss(mocker):
    cache = _mock_cache(mocker, get_return=None)
    fetched_policies = [_make_policy()]
    db = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = fetched_policies
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db.execute = AsyncMock(return_value=execute_result)

    result = await PolicyRepository.get_active_policies_for_user("user@example.com", db)

    assert result == fetched_policies
    db.execute.assert_awaited_once()
    cache.set_user_policies.assert_awaited_once_with("user@example.com", fetched_policies)


# ---------------------------- Invalidation on policy update/delete (global) ----------------------------

@pytest.mark.asyncio
async def test_update_policy_invalidates_all_user_policy_caches(mocker):
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    mocker.patch(f"{REPO_MODULE}.policy_history_repository")
    cache = _mock_cache(mocker)

    await PolicyRepository.update(_make_policy(), {"description": "new"}, db)

    cache.invalidate_all_user_policies.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_policy_invalidates_all_user_policy_caches(mocker):
    db = MagicMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    mocker.patch(f"{REPO_MODULE}.policy_history_repository")
    cache = _mock_cache(mocker)

    await PolicyRepository.delete(_make_policy(), db)

    cache.invalidate_all_user_policies.assert_awaited_once()


# ---------------------------- Invalidation on assign/revoke (precise) ----------------------------

@pytest.mark.asyncio
async def test_assign_policy_to_user_invalidates_only_that_users_cache_when_email_given(mocker):
    cache = _mock_cache(mocker)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    await PolicyRepository.assign_policy_to_user(
        user_id=1, policy_id=2, db=db, assigned_by="admin@example.com", user_email="target@example.com"
    )

    cache.invalidate_user_policies.assert_awaited_once_with("target@example.com")
    cache.invalidate_all_user_policies.assert_not_called()


@pytest.mark.asyncio
async def test_assign_policy_to_user_skips_invalidation_when_email_not_given(mocker):
    """Backward-compatible: system-side self-assignment (signup, OAuth2,
    create_system_user.py) doesn't pass user_email : a brand-new user has
    nothing cached to invalidate, so this must not error or invalidate
    anything global."""
    cache = _mock_cache(mocker)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    await PolicyRepository.assign_policy_to_user(user_id=1, policy_id=2, db=db, assigned_by="system")

    cache.invalidate_user_policies.assert_not_called()


@pytest.mark.asyncio
async def test_remove_policy_from_user_invalidates_only_that_users_cache_when_email_given(mocker):
    cache = _mock_cache(mocker)
    db = MagicMock()
    existing_assignment = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_assignment)))
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    removed = await PolicyRepository.remove_policy_from_user(
        user_id=1, policy_id=2, db=db, user_email="target@example.com"
    )

    assert removed is True
    cache.invalidate_user_policies.assert_awaited_once_with("target@example.com")
