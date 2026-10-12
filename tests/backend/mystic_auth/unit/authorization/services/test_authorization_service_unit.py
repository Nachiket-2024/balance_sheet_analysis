# Unit coverage for AuthorizationService, the centralized layer routes and
# services go through: Request -> Authentication -> Authorization Service ->
# Policy Evaluation Engine -> Allow/Deny. These tests mock the repository (DB
# boundary) and exercise the real evaluator underneath, confirming the service
# wires "fetch policies, ask the engine" correctly and that require() raises
# 403 on denial. Audit logging is covered in
# test_authorization_service_audit_log_unit.py, and authorize_batch in
# test_authorization_service_batch_unit.py.
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

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
    """authorize()/require() always queue an audit entry via
    log_authorization_decision_task. Mocked explicitly here rather than relying
    on log_decision's own try/except, which would otherwise silently swallow a
    real attempt to reach Procrastinate's DB, unavailable in unit tests."""
    return mocker.patch(f"{AUDIT_MODULE}.log_authorization_decision_task.defer_async", new_callable=AsyncMock)


# ---------------------------- Audit logging is queued, not written inline ----------------------------
# log_decision defers log_authorization_decision_task rather than writing the
# audit row inline, so the INSERT happens in a background worker off the
# request path. This suite covers that: the right entry gets queued exactly
# once, and a queueing failure never breaks the real decision.

@pytest.mark.asyncio
async def test_authorize_queues_exactly_one_audit_entry_per_call(mocker):
    log_mock = _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"])],
    )

    await authorization_service.authorize("admin@example.com", "users:list_all", "users", db=None)

    log_mock.assert_called_once()


@pytest.mark.asyncio
async def test_authorize_queues_an_audit_entry_matching_the_computed_decision(mocker):
    """The queued entry must reflect the real decision (who, what, on what,
    allowed or not, and which policies granted it), not a placeholder: it's
    the only record of the decision until the worker persists it."""
    log_mock = _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_management")],
    )

    await authorization_service.authorize(
        "admin@example.com", "users:list_all", "users", db=None,
        resource={"email": "target@example.com"}, context={"ip_address": "203.0.113.7"},
    )

    entry = log_mock.call_args.kwargs["entry"]
    assert entry["user_email"] == "admin@example.com"
    assert entry["action"] == "users:list_all"
    assert entry["resource_type"] == "users"
    assert entry["resource_identifier"] == "target@example.com"
    assert entry["allowed"] is True
    assert entry["granting_policy_names"] == ["user_management"]
    assert entry["context"] == {"ip_address": "203.0.113.7"}


@pytest.mark.asyncio
async def test_authorize_queues_a_denied_entry_with_no_granting_policies(mocker):
    log_mock = _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:read_own"])],
    )

    await authorization_service.authorize("user@example.com", "users:list_all", "users", db=None)

    entry = log_mock.call_args.kwargs["entry"]
    assert entry["allowed"] is False
    assert entry["granting_policy_names"] == []


@pytest.mark.asyncio
async def test_authorize_detailed_never_queues_an_audit_entry(mocker):
    """authorize_detailed is the hypothetical "what would happen if" path
    (the inspection endpoint); it must never queue an audit job."""
    log_mock = _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"])],
    )

    await authorization_service.authorize_detailed("admin@example.com", "users:list_all", "users", db=None)

    log_mock.assert_not_called()


@pytest.mark.asyncio
async def test_authorize_returns_true_when_a_fetched_policy_grants_the_action(mocker):
    _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"])],
    )

    result = await authorization_service.authorize("admin@example.com", "users:list_all", "users", db=None)

    assert result is True


@pytest.mark.asyncio
async def test_authorize_returns_false_when_no_fetched_policy_grants_the_action(mocker):
    _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:read_own"])],
    )

    result = await authorization_service.authorize("user@example.com", "users:list_all", "users", db=None)

    assert result is False


@pytest.mark.asyncio
async def test_authorize_returns_false_for_a_user_with_no_assigned_policies(mocker):
    _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )

    result = await authorization_service.authorize("nobody@example.com", "users:read_own", "users", db=None)

    assert result is False


@pytest.mark.asyncio
async def test_require_raises_403_when_denied(mocker):
    _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await authorization_service.require("user@example.com", "users:list_all", "users", db=None)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_does_not_raise_when_allowed(mocker):
    _mock_audit_log(mocker)
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"])],
    )

    # Should not raise
    await authorization_service.require("admin@example.com", "users:list_all", "users", db=None)


@pytest.mark.asyncio
async def test_authorize_passes_resource_through_for_ownership_conditions(mocker):
    _mock_audit_log(mocker)
    self_only_policy = Policy(
        actions=["documents:read"], resource_type="documents", conditions={"self_only": True}, is_active=True
    )
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[self_only_policy],
    )

    owned = await authorization_service.authorize(
        "user@example.com", "documents:read", "documents", db=None, resource={"email": "user@example.com"}
    )
    not_owned = await authorization_service.authorize(
        "user@example.com", "documents:read", "documents", db=None, resource={"email": "someone-else@example.com"}
    )

    assert owned is True
    assert not_owned is False


# ---------------------------- authorize_detailed (explainability) ----------------------------
# authorize_detailed returns an AuthorizationDecision from
# evaluators/authorization_decision.py so callers get the structured
# explanation behind the decision.

@pytest.mark.asyncio
async def test_authorize_detailed_reports_matched_policies(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_management")],
    )

    decision = await authorization_service.authorize_detailed(
        "admin@example.com", "users:list_all", "users", db=None
    )

    assert decision.allowed is True
    assert decision.matched_policies == ["user_management"]
    assert decision.rejected_policies == []
    assert decision.denial_reason is None


@pytest.mark.asyncio
async def test_authorize_detailed_distinguishes_matched_from_rejected_on_condition_failure(mocker):
    conditioned_policy = _policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}},
        name="publish_drafts",
    )
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[conditioned_policy],
    )

    decision = await authorization_service.authorize_detailed(
        "editor@example.com", "documents:publish", "documents", db=None,
        resource={"status": "published"},
    )

    assert decision.allowed is False
    assert decision.matched_policies == []
    assert decision.rejected_policies == ["publish_drafts"]
    assert decision.failed_conditions == {"publish_drafts": ["resource_attributes"]}
    assert decision.denial_reason == "condition_failed"
