# tests/backend/mystic_auth/unit/api/pbac_routes/test_policy_history_unit.py
#
# Unit coverage for policy versioning and rollback (the policy
# History": immutable history, version comparison, rollback support).
# PolicyRepository's create/update/delete are exercised with the
# policy_history_repository mocked out (DB boundary); the route-level
# compare/rollback handlers are called directly the same way FastAPI would
# inject them.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.api.pbac_routes.policy_history_routes import (
    _definition_for_entry,
    compare_policy_history,
    rollback_policy,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    PolicyRepository,
    _definition_snapshot,
)
from backend.mystic_auth.authorization.schemas.policy_history_schema import (
    PolicyRollbackRequest,
)
from fastapi import HTTPException

REPO_MODULE = "backend.mystic_auth.authorization.repositories.policy_repository"
ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.policy_history_routes"
SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"


# ---------------------------- Helpers ----------------------------
def _make_policy(**overrides):
    policy = MagicMock()
    policy.id = 1
    policy.name = "self_service"
    policy.description = "baseline"
    policy.actions = ["users:read_own"]
    policy.resource_type = "users"
    policy.conditions = {"self_only": True}
    policy.is_active = True
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


def _make_history_entry(**overrides):
    entry = MagicMock()
    entry.id = 1
    entry.policy_name = "self_service"
    entry.change_type = "updated"
    entry.previous_definition = {"actions": ["users:read_own"]}
    entry.new_definition = {"actions": ["users:read_own", "users:update_own"]}
    for key, value in overrides.items():
        setattr(entry, key, value)
    return entry


# ---------------------------- Repository: Create Writes History ----------------------------
@pytest.mark.asyncio
async def test_create_policy_writes_created_history_entry(mocker):
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    created_policy = _make_policy()
    mocker.patch(f"{REPO_MODULE}.Policy", return_value=created_policy)
    mock_history_repo = mocker.patch(f"{REPO_MODULE}.policy_history_repository")

    await PolicyRepository.create(
        {"name": "self_service", "actions": ["users:read_own"], "resource_type": "users"},
        db,
        changed_by="admin@example.com",
    )

    history_data = mock_history_repo.add_entry.call_args[0][0]
    assert history_data["change_type"] == "created"
    assert history_data["previous_definition"] is None
    assert history_data["new_definition"]["actions"] == ["users:read_own"]
    assert history_data["changed_by"] == "admin@example.com"


# ---------------------------- Repository: Update Writes History with Diff ----------------------------
@pytest.mark.asyncio
async def test_update_policy_writes_updated_history_with_changed_fields(mocker):
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    policy = _make_policy()
    mock_history_repo = mocker.patch(f"{REPO_MODULE}.policy_history_repository")
    mocker.patch(f"{REPO_MODULE}.authorization_cache_service", new=MagicMock(
        invalidate_all_user_policies=AsyncMock()
    ))

    await PolicyRepository.update(
        policy,
        {"actions": ["users:read_own", "users:update_own"]},
        db,
        changed_by="admin@example.com",
        change_reason="expand grant",
    )

    history_data = mock_history_repo.add_entry.call_args[0][0]
    assert history_data["change_type"] == "updated"
    assert history_data["changed_fields"] == ["actions"]
    assert history_data["previous_definition"]["actions"] == ["users:read_own"]
    assert history_data["new_definition"]["actions"] == ["users:read_own", "users:update_own"]
    assert history_data["change_reason"] == "expand grant"


@pytest.mark.asyncio
async def test_update_policy_can_be_labeled_as_rolled_back(mocker):
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    policy = _make_policy()
    mock_history_repo = mocker.patch(f"{REPO_MODULE}.policy_history_repository")
    mocker.patch(f"{REPO_MODULE}.authorization_cache_service", new=MagicMock(
        invalidate_all_user_policies=AsyncMock()
    ))

    await PolicyRepository.update(
        policy, {"actions": ["users:read_own"]}, db,
        changed_by="admin@example.com",
        change_reason="Rolled back to history entry 5",
        change_type="rolled_back",
    )

    history_data = mock_history_repo.add_entry.call_args[0][0]
    assert history_data["change_type"] == "rolled_back"


# ---------------------------- Repository: Delete Writes History, Preserves Definition ----------------------------
@pytest.mark.asyncio
async def test_delete_policy_writes_deleted_history_entry(mocker):
    db = MagicMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    policy = _make_policy()
    mock_history_repo = mocker.patch(f"{REPO_MODULE}.policy_history_repository")
    mocker.patch(f"{REPO_MODULE}.authorization_cache_service", new=MagicMock(
        invalidate_all_user_policies=AsyncMock()
    ))

    await PolicyRepository.delete(policy, db, changed_by="admin@example.com", change_reason="cleanup")

    history_data = mock_history_repo.add_entry.call_args[0][0]
    assert history_data["change_type"] == "deleted"
    assert history_data["previous_definition"]["name"] == "self_service"
    assert history_data["new_definition"] is None
    db.delete.assert_awaited_once_with(policy)


def test_definition_snapshot_only_includes_definitional_fields():
    snapshot = _definition_snapshot(_make_policy())
    assert set(snapshot.keys()) == {
        "name", "description", "actions", "resource_type", "conditions", "is_active",
    }


# ---------------------------- Compare Route ----------------------------
@pytest.mark.asyncio
async def test_compare_policy_history_returns_diff(mocker):
    from_entry = _make_history_entry(id=1, new_definition={"actions": ["users:read_own"], "is_active": True})
    to_entry = _make_history_entry(
        id=2, new_definition={"actions": ["users:read_own", "users:update_own"], "is_active": True}
    )
    mocker.patch(
        f"{ROUTES_MODULE}.policy_history_repository.get_by_id",
        new_callable=AsyncMock, side_effect=[from_entry, to_entry],
    )

    result = await compare_policy_history(
        policy_name="self_service", from_id=1, to_id=2,
        current_user={"email": "admin@example.com"}, db="fake-db",
    )

    assert result.changed_fields == ["actions"]
    assert result.diff["actions"]["from"] == ["users:read_own"]
    assert result.diff["actions"]["to"] == ["users:read_own", "users:update_own"]


@pytest.mark.asyncio
async def test_compare_policy_history_rejects_mismatched_policy_name(mocker):
    from_entry = _make_history_entry(id=1, policy_name="self_service")
    to_entry = _make_history_entry(id=2, policy_name="user_administration")
    mocker.patch(
        f"{ROUTES_MODULE}.policy_history_repository.get_by_id",
        new_callable=AsyncMock, side_effect=[from_entry, to_entry],
    )

    with pytest.raises(HTTPException) as exc_info:
        await compare_policy_history(
            policy_name="self_service", from_id=1, to_id=2,
            current_user={"email": "admin@example.com"}, db="fake-db",
        )

    assert exc_info.value.status_code == 400


# ---------------------------- Rollback Route ----------------------------
@pytest.mark.asyncio
async def test_rollback_policy_applies_target_definition_and_labels_history(mocker):
    policy = _make_policy()
    target_definition = {
        "name": "self_service", "description": "baseline", "actions": ["users:read_own"],
        "resource_type": "users", "conditions": {"self_only": True}, "is_active": True,
    }
    history_entry = _make_history_entry(id=5, policy_name="self_service", new_definition=target_definition)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ROUTES_MODULE}.policy_history_repository.get_by_id", new_callable=AsyncMock, return_value=history_entry)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=True)

    await rollback_policy(
        policy_name="self_service", history_id=5,
        rollback_request=PolicyRollbackRequest(reason="revert bad change"),
        current_user={"email": "admin@example.com"}, db="fake-db",
    )

    update_mock.assert_awaited_once_with(
        policy, target_definition, "fake-db",
        changed_by="admin@example.com",
        change_reason="revert bad change",
        change_type="rolled_back",
    )


@pytest.mark.asyncio
async def test_rollback_policy_to_deleted_entry_restores_previous_definition(mocker):
    """A "deleted" history entry has no new_definition, but its
    previous_definition (the state right before deletion) is still a valid
    rollback target : _definition_for_entry falls back to it."""
    policy = _make_policy()
    pre_deletion_definition = {"name": "self_service", "actions": ["users:read_own"]}
    deleted_entry = _make_history_entry(
        id=9, policy_name="self_service", change_type="deleted",
        previous_definition=pre_deletion_definition, new_definition=None,
    )
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ROUTES_MODULE}.policy_history_repository.get_by_id", new_callable=AsyncMock, return_value=deleted_entry)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=True)

    await rollback_policy(
        policy_name="self_service", history_id=9, rollback_request=None,
        current_user={"email": "admin@example.com"}, db="fake-db",
    )

    update_mock.assert_awaited_once_with(
        policy, pre_deletion_definition, "fake-db",
        changed_by="admin@example.com",
        change_reason="Rolled back to history entry 9",
        change_type="rolled_back",
    )


@pytest.mark.asyncio
async def test_rollback_policy_rejects_entry_belonging_to_another_policy(mocker):
    policy = _make_policy()
    other_policy_entry = _make_history_entry(id=9, policy_name="user_administration")
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ROUTES_MODULE}.policy_history_repository.get_by_id", new_callable=AsyncMock, return_value=other_policy_entry)

    with pytest.raises(HTTPException) as exc_info:
        await rollback_policy(
            policy_name="self_service", history_id=9, rollback_request=None,
            current_user={"email": "admin@example.com"}, db="fake-db",
        )

    assert exc_info.value.status_code == 404


def test_definition_for_entry_falls_back_to_previous_when_deleted():
    deleted_entry = _make_history_entry(new_definition=None, previous_definition={"name": "self_service"})
    assert _definition_for_entry(deleted_entry) == {"name": "self_service"}


def test_definition_for_entry_uses_new_definition_when_present():
    entry = _make_history_entry(new_definition={"name": "x"}, previous_definition={"name": "y"})
    assert _definition_for_entry(entry) == {"name": "x"}
