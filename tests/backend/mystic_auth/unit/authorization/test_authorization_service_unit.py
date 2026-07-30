# tests/backend/mystic_auth/unit/test_authorization_service_unit.py
#
# Unit coverage for AuthorizationService, the centralized layer routes and
# services must go through per claude.md's target flow:
#   Request -> Authentication -> Authorization Service
#           -> Policy Evaluation Engine -> Allow / Deny
# These tests mock the repository (DB boundary) and exercise the real
# evaluator underneath, confirming the service wires "fetch policies, ask
# the engine" correctly and that require() raises 403 on denial.
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.authorization.models.policy_model import Policy
from backend.mystic_auth.authorization.services.authorization_service import authorization_service
from fastapi import HTTPException

MODULE = "backend.mystic_auth.authorization.services.authorization_service"


def _policy(actions, resource_type="users", conditions=None, name=None):
    return Policy(
        name=name, actions=actions, resource_type=resource_type, conditions=conditions, is_active=True
    )


def _mock_audit_log(mocker):
    """authorize()/require() always write an audit entry (see
    _log_decision); mocked explicitly in tests that don't care about the
    audit trail itself, rather than relying on _log_decision's own
    try/except (which would otherwise silently swallow the AttributeError
    from calling db.add() on the db=None these tests pass)."""
    return mocker.patch(f"{MODULE}.audit_log_repository.create_entry", new_callable=AsyncMock)


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
# authorize_detailed now returns an AuthorizationDecision (see
# evaluators/authorization_decision.py), per claude.md's Authorization
# Decision Explainability, "detailed APIs should use new structure".

@pytest.mark.asyncio
async def test_authorize_detailed_reports_matched_policies(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_administration")],
    )

    decision = await authorization_service.authorize_detailed(
        "admin@example.com", "users:list_all", "users", db=None
    )

    assert decision.allowed is True
    assert decision.matched_policies == ["user_administration"]
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


# ---------------------------- Automatic audit logging ----------------------------
# Per claude.md's Remaining PBAC Work: "Automatically log every authorize()
# call". Logged inside authorize() (not authorize_detailed) so the
# authorization-check inspection endpoint's hypothetical "what would happen
# if" queries, which call authorize_detailed directly, never pollute the
# audit trail with decisions nothing actually acted on.

@pytest.mark.asyncio
async def test_authorize_writes_an_audit_log_entry_with_the_decision(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_administration")],
    )
    log_mock = _mock_audit_log(mocker)

    await authorization_service.authorize("admin@example.com", "users:list_all", "users", db="fake-db")

    log_mock.assert_awaited_once()
    entry_data, db_arg = log_mock.await_args.args
    assert entry_data["user_email"] == "admin@example.com"
    assert entry_data["action"] == "users:list_all"
    assert entry_data["resource_type"] == "users"
    assert entry_data["allowed"] is True
    assert entry_data["candidate_policy_names"] == ["user_administration"]
    assert entry_data["granting_policy_names"] == ["user_administration"]
    assert entry_data["failed_conditions"] is None
    assert db_arg == "fake-db"


@pytest.mark.asyncio
async def test_authorize_writes_failed_conditions_for_a_rejected_policy(mocker):
    """claude.md: 'audit logs should capture explanation': a denial
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

    entry_data = log_mock.await_args.args[0]
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

    entry_data = log_mock.await_args.args[0]
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

    entry_data = log_mock.await_args.args[0]
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

    entry_data = log_mock.await_args.args[0]
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
        "admin@example.com", "users:delete_any", "users", db=None,
        context={"mfa_verified": True},
    )

    entry_data = log_mock.await_args.args[0]
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
        f"{MODULE}.audit_log_repository.create_entry",
        new_callable=AsyncMock,
        side_effect=Exception("db is down"),
    )

    result = await authorization_service.authorize("admin@example.com", "users:list_all", "users", db=None)

    assert result is True


# ---------------------------- authorize_batch ----------------------------
# claude.md's Batch Authorization API: "reuse the existing AuthorizationService
# and AuthorizationDecision flow", "avoid repeated policy database queries
# inside one batch request", "single authorization and batch authorization
# must produce identical authorization decisions", "fail closed for invalid
# individual checks".

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
        {"action": "users:delete_any", "resource_type": "users", "resource": None},
    ]

    await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    get_policies_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_authorize_batch_returns_mixed_allowed_and_denied_decisions(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_administration")],
    )
    _mock_audit_log(mocker)

    checks = [
        {"action": "users:list_all", "resource_type": "users", "resource": None},
        {"action": "users:delete_any", "resource_type": "users", "resource": None},
    ]

    decisions = await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    assert [d.allowed for d in decisions] == [True, False]
    assert decisions[0].action == "users:list_all"
    assert decisions[1].action == "users:delete_any"
    assert decisions[1].denial_reason == "no_matching_policy"


@pytest.mark.asyncio
async def test_authorize_batch_logs_every_check_individually(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:list_all"], name="user_administration")],
    )
    log_mock = _mock_audit_log(mocker)

    checks = [
        {"action": "users:list_all", "resource_type": "users", "resource": None},
        {"action": "users:delete_any", "resource_type": "users", "resource": None},
    ]

    await authorization_service.authorize_batch("admin@example.com", checks, db=None)

    assert log_mock.await_count == 2


@pytest.mark.asyncio
async def test_authorize_batch_matches_individual_authorize_calls_for_the_same_checks(mocker):
    """The exact requirement: single authorization and batch authorization
    must produce identical authorization decisions."""
    policies = [_policy(["users:list_all"], name="user_administration")]
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
        return_value=[_policy(["users:list_all"], name="user_administration")],
    )
    _mock_audit_log(mocker)

    from backend.mystic_auth.authorization.evaluators.policy_evaluator import PolicyEvaluationEngine

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
