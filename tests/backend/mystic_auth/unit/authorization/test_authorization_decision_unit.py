# tests/backend/mystic_auth/unit/test_authorization_decision_unit.py
#
# Focused coverage for claude.md's Authorization Decision Explainability
# named test list: allowed-because-matched, denied-because-no-match,
# denied-because-condition-failed, denied-because-invalid-context,
# multiple-policies-one-grants-one-fails, plus the security requirement
# that require()'s user-facing error stays generic (never leaks which
# policies were evaluated/rejected).
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.authorization.evaluators.policy_evaluator import PolicyEvaluationEngine
from backend.mystic_auth.authorization.models.policy_model import Policy
from backend.mystic_auth.authorization.services.authorization_service import authorization_service
from fastapi import HTTPException

MODULE = "backend.mystic_auth.authorization.services.authorization_service"


def _policy(actions, resource_type="users", conditions=None, name=None):
    return Policy(name=name, actions=actions, resource_type=resource_type, conditions=conditions, is_active=True)


# ---------------------------- Allowed because policy matched ----------------------------

def test_allowed_because_a_policy_matched():
    decision = PolicyEvaluationEngine.evaluate_detailed(
        [_policy(["users:list_all"], name="user_administration")],
        "users:list_all", "users", "admin@example.com",
    )
    assert decision.allowed is True
    assert decision.matched_policies == ["user_administration"]
    assert decision.denial_reason is None


# ---------------------------- Denied because no policy matched ----------------------------

def test_denied_because_no_policy_matched_the_action():
    decision = PolicyEvaluationEngine.evaluate_detailed(
        [_policy(["users:read_own"], name="self_service")],
        "users:list_all", "users", "user@example.com",
    )
    assert decision.allowed is False
    assert decision.matched_policies == []
    assert decision.rejected_policies == []
    assert decision.denial_reason == "no_matching_policy"


def test_denied_because_no_policies_assigned_at_all():
    decision = PolicyEvaluationEngine.evaluate_detailed(
        [], "users:list_all", "users", "user@example.com",
    )
    assert decision.allowed is False
    assert decision.denial_reason == "no_assigned_policies"


# ---------------------------- Denied because condition failed ----------------------------

def test_denied_because_condition_failed():
    policy = _policy(
        ["documents:publish"], resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}}, name="publish_drafts",
    )
    decision = PolicyEvaluationEngine.evaluate_detailed(
        [policy], "documents:publish", "documents", "editor@example.com",
        resource={"status": "published"},
    )
    assert decision.allowed is False
    assert decision.rejected_policies == ["publish_drafts"]
    assert decision.failed_conditions == {"publish_drafts": ["resource_attributes"]}
    assert decision.denial_reason == "condition_failed"


# ---------------------------- Denied because invalid/missing context ----------------------------

def test_denied_because_required_context_is_missing():
    """A network-gated policy with no context at all (no ip_address to
    check) must deny and report exactly which condition failed."""
    policy = _policy(
        ["reports:view"], resource_type="reports",
        conditions={"network": {"allowed_ips": ["10.0.0.0/8"]}}, name="office_only",
    )
    decision = PolicyEvaluationEngine.evaluate_detailed(
        [policy], "reports:view", "reports", "user@example.com", context=None,
    )
    assert decision.allowed is False
    assert decision.rejected_policies == ["office_only"]
    assert decision.failed_conditions == {"office_only": ["network"]}
    assert decision.denial_reason == "condition_failed"


# ---------------------------- Multiple policies: one grants, one fails ----------------------------

def test_multiple_policies_one_grants_and_one_fails():
    granting_policy = _policy(["documents:publish"], resource_type="documents", name="unconditional_publisher")
    failing_policy = _policy(
        ["documents:publish"], resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}}, name="draft_only_publisher",
    )
    decision = PolicyEvaluationEngine.evaluate_detailed(
        [granting_policy, failing_policy], "documents:publish", "documents", "editor@example.com",
        resource={"status": "published"},
    )
    assert decision.allowed is True
    assert decision.matched_policies == ["unconditional_publisher"]
    assert decision.rejected_policies == ["draft_only_publisher"]
    assert decision.failed_conditions == {"draft_only_publisher": ["resource_attributes"]}
    assert decision.denial_reason is None  # allowed overall, despite one rejection


# ---------------------------- Security: user-facing errors stay generic ----------------------------

@pytest.mark.asyncio
async def test_require_raises_a_generic_error_never_leaking_policy_details(mocker):
    """claude.md: 'Never expose sensitive policy details to unauthorized
    users. User-facing errors should remain generic.' require() must
    surface only a generic 403, regardless of how much detail
    AuthorizationDecision carries internally."""
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_policy(["users:read_own"], name="self_service")],
    )
    mocker.patch(f"{MODULE}.audit_log_repository.create_entry", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await authorization_service.require("user@example.com", "users:list_all", "users", db=None)

    assert exc_info.value.status_code == 403
    detail = str(exc_info.value.detail)
    assert "self_service" not in detail
    assert "no_matching_policy" not in detail
