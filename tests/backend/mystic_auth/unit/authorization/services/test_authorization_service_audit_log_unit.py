# Every authorize() call must be logged. Logged inside authorize() (not
# authorize_detailed) so the inspection endpoint's "what would happen if" queries,
# which call authorize_detailed directly, never pollute the audit trail with
# decisions nothing actually acted on. Split out of test_authorization_service_unit.py,
# which has the base authorize()/require() coverage this builds on.
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.authorization.models.policy_model import Policy
from backend.mystic_auth.authorization.services.authorization_service import (
    authorization_service,
)

MODULE = "backend.mystic_auth.authorization.services.authorization_service"
AUDIT_MODULE = "backend.mystic_auth.authorization.services.authorization_audit_logger"


def _policy(actions, resource_type="users", conditions=None, name=None):
    return Policy(
        name=name, actions=actions, resource_type=resource_type, conditions=conditions, is_active=True
    )


def _mock_audit_log(mocker):
    return mocker.patch(f"{AUDIT_MODULE}.log_authorization_decision_task.defer_async", new_callable=AsyncMock)


@pytest.mark.asyncio
async def test_authorize_writes_an_audit_log_entry_with_the_decision(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_management")],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize("admin@example.com", "users:list_all", "users", db="fake-db")

    log_mock.assert_awaited_once()
    entry_data = log_mock.await_args.kwargs["entry"]
    assert entry_data["user_email"] == "admin@example.com"
    assert entry_data["action"] == "users:list_all"
    assert entry_data["resource_type"] == "users"
    assert entry_data["allowed"] is True
    assert entry_data["candidate_policy_names"] == ["user_management"]
    assert entry_data["granting_policy_names"] == ["user_management"]
    assert entry_data["failed_conditions"] is None


@pytest.mark.asyncio
async def test_authorize_writes_failed_conditions_for_a_rejected_policy(mocker):
    """'audit logs should capture explanation': a denial
    caused by a failed condition must be traceable from the audit trail
    alone, without re-running the evaluation."""
    conditioned_policy = _policy(
        ["documents:publish"], resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}}, name="publish_drafts",
    )
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[conditioned_policy],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize(
        "editor@example.com", "documents:publish", "documents", db="fake-db",
        resource={"status": "published"},
    )

    entry_data = log_mock.await_args.kwargs["entry"]
    assert entry_data["allowed"] is False
    assert entry_data["candidate_policy_names"] == ["publish_drafts"]
    assert entry_data["granting_policy_names"] == []
    assert entry_data["failed_conditions"] == {"publish_drafts": ["resource_attributes"]}


@pytest.mark.asyncio
async def test_authorize_logs_a_denial_with_no_granting_policies(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize("user@example.com", "users:list_all", "users", db=None)

    entry_data = log_mock.await_args.kwargs["entry"]
    assert entry_data["allowed"] is False
    assert entry_data["candidate_policy_names"] == []
    assert entry_data["granting_policy_names"] == []


@pytest.mark.asyncio
async def test_authorize_log_entry_extracts_resource_identifier_from_dict_email(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize(
        "admin@example.com", "users:update_any", "users", db=None,
        resource={"email": "target@example.com"},
    )

    entry_data = log_mock.await_args.kwargs["entry"]
    assert entry_data["resource_identifier"] == "target@example.com"


@pytest.mark.asyncio
async def test_authorize_log_entry_has_no_resource_identifier_when_no_resource_given(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize("admin@example.com", "users:list_all", "users", db=None)

    entry_data = log_mock.await_args.kwargs["entry"]
    assert entry_data["resource_identifier"] is None


@pytest.mark.asyncio
async def test_authorize_log_entry_carries_the_supplied_context(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize(
        "admin@example.com", "users:deactivate_any", "users", db=None,
        context={"mfa_verified": True},
    )

    entry_data = log_mock.await_args.kwargs["entry"]
    assert entry_data["context"] == {"mfa_verified": True}


@pytest.mark.asyncio
async def test_authorize_detailed_does_not_write_an_audit_log_entry(mocker):
    # Calling authorize_detailed directly (as the inspection endpoint does)
    # must not produce an audit entry; only real authorize()/require()
    # calls do.
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"])],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize_detailed("admin@example.com", "users:list_all", "users", db=None)

    log_mock.assert_not_called()


@pytest.mark.asyncio
async def test_authorize_still_returns_correctly_even_if_audit_logging_fails(mocker):
    # A logging failure must never break the actual authorization decision.
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"])],
    )
    mocker.patch(
        f"{AUDIT_MODULE}.log_authorization_decision_task.defer_async",
        new_callable=AsyncMock,
        side_effect=Exception("db is down"),
    )

    result = await authorization_service.authorize("admin@example.com", "users:list_all", "users", db=None)

    assert result is True
