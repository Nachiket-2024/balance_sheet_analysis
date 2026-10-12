# Coverage for AuthorizationService.authorize_batch: it must avoid repeated
# policy database queries within one batch request, produce decisions identical
# to single authorize() calls, and fail closed for invalid individual checks.
# Split out of test_authorization_service_unit.py.
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
async def test_authorize_batch_fetches_policies_exactly_once_for_the_whole_batch(mocker):
    get_policies_mock = mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all", "users:read_own"], name="mixed")],
    )
    _mock_audit_log(mocker)

    checks = [
        {"action": "users:list_all", "resource_type": "users", "resource": None},
        {"action": "users:read_own", "resource_type": "users", "resource": None},
        {"action": "users:deactivate_any", "resource_type": "users", "resource": None},
    ]

    await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    get_policies_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_authorize_batch_returns_mixed_allowed_and_denied_decisions(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_management")],
    )
    _mock_audit_log(mocker)

    checks = [
        {"action": "users:list_all", "resource_type": "users", "resource": None},
        {"action": "users:deactivate_any", "resource_type": "users", "resource": None},
    ]

    decisions = await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    assert [d.allowed for d in decisions] == [True, False]
    assert decisions[0].action == "users:list_all"
    assert decisions[1].action == "users:deactivate_any"
    assert decisions[1].denial_reason == "no_matching_policy"


@pytest.mark.asyncio
async def test_authorize_batch_logs_every_check_in_one_bulk_write(mocker):
    """Every check still gets its own audit row, but authorize_batch
    persists them all in a single create_entries call rather than one
    create_entry commit per check - see authorization_service.py's
    authorize_batch docstring for why (up to 50 checks per batch)."""
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_management")],
    )
    bulk_log_mock = mocker.patch(
        f"{MODULE}.authorization_audit_log_repository.create_entries", new_callable=AsyncMock
    )

    checks = [
        {"action": "users:list_all", "resource_type": "users", "resource": None},
        {"action": "users:deactivate_any", "resource_type": "users", "resource": None},
    ]

    await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    assert bulk_log_mock.await_count == 1
    logged_entries = bulk_log_mock.await_args.args[0]
    assert len(logged_entries) == 2
    assert [entry["action"] for entry in logged_entries] == ["users:list_all", "users:deactivate_any"]


@pytest.mark.asyncio
async def test_authorize_batch_matches_individual_authorize_calls_for_the_same_checks(mocker):
    """The exact requirement: single authorization and batch authorization
    must produce identical authorization decisions."""
    policies = [_policy(["users:list_all"], name="user_management")]
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=policies,
    )
    _mock_audit_log(mocker)

    checks = [
        {"action": "users:list_all", "resource_type": "users", "resource": None},
        {"action": "users:read_own", "resource_type": "users", "resource": None},
    ]

    batch_decisions = await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    for check, batch_decision in zip(checks, batch_decisions, strict=True):
        individual_result = await authorization_service.authorize(
            "admin@example.com", check["action"], check["resource_type"], db=None
        )
        assert batch_decision.allowed == individual_result


@pytest.mark.asyncio
async def test_authorize_batch_fails_closed_when_one_check_raises_during_evaluation(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_management")],
    )
    _mock_audit_log(mocker)

    from backend.mystic_auth.authorization.evaluators.policy_evaluator import (
        PolicyEvaluationEngine,
    )

    call_count = {"n": 0}

    def _side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("corrupt policy row")
        return PolicyEvaluationEngine.evaluate_detailed(*args, **kwargs)

    mocker.patch(f"{MODULE}.policy_evaluation_engine.evaluate_detailed", side_effect=_side_effect)

    checks = [
        {"action": "users:list_all", "resource_type": "users", "resource": None},
        {"action": "users:list_all", "resource_type": "users", "resource": None},
    ]

    decisions = await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    assert decisions[0].allowed is False
    assert decisions[0].denial_reason == "evaluation_error"
    assert decisions[1].allowed is True  # the rest of the batch still evaluated normally


@pytest.mark.asyncio
async def test_authorize_batch_empty_checks_returns_empty_decisions(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )

    decisions = await authorization_service.authorize_batch("admin@example.com", [], db=None)

    assert decisions == []
