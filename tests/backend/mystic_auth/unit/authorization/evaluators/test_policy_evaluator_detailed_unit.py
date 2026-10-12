# Unit coverage for PolicyEvaluationEngine.evaluate_detailed's explainability
# contract: it returns an AuthorizationDecision (matched_policies/rejected_policies)
# rather than a bare dict. Split out of test_policy_evaluator_unit.py, which has
# the base allow/deny/conditions coverage this builds on.

from backend.mystic_auth.authorization.evaluators.policy_evaluator import (
    PolicyEvaluationEngine,
)
from backend.mystic_auth.authorization.models.policy_model import Policy


def _policy(actions, resource_type="users", conditions=None, name=None):
    return Policy(
        name=name, actions=actions, resource_type=resource_type, conditions=conditions, is_active=True
    )


def test_evaluate_detailed_reports_empty_lists_and_no_assigned_policies_reason_when_no_policies_held():
    decision = PolicyEvaluationEngine.evaluate_detailed([], "users:list_all", "users", "user@example.com")

    assert decision.allowed is False
    assert decision.evaluated_policies == []
    assert decision.matched_policies == []
    assert decision.rejected_policies == []
    assert decision.failed_conditions == {}
    assert decision.denial_reason == "no_assigned_policies"
    assert decision.evaluation_timestamp  # a non-empty ISO timestamp was set


def test_evaluate_detailed_agrees_with_evaluate_on_unconditional_allow():
    policies = [_policy(["users:list_all"], name="admin_policy")]

    decision = PolicyEvaluationEngine.evaluate_detailed(
        policies, "users:list_all", "users", "admin@example.com"
    )

    assert decision.allowed is True
    assert decision.matched_policies == ["admin_policy"]
    assert decision.rejected_policies == []
    assert decision.denial_reason is None


def test_evaluate_detailed_lists_a_policy_as_rejected_with_its_failed_condition_when_conditions_fail():
    # The point of evaluate_detailed over evaluate: telling apart "no policy even
    # applies" from "a policy applies but its conditions rejected this resource",
    # and which condition key failed.
    policy = _policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}},
        name="publish_drafts",
    )

    decision = PolicyEvaluationEngine.evaluate_detailed(
        [policy], "documents:publish", "documents", "editor@example.com",
        resource={"status": "published"},
    )

    assert decision.allowed is False
    assert decision.matched_policies == []
    assert decision.rejected_policies == ["publish_drafts"]
    assert decision.failed_conditions == {"publish_drafts": ["resource_attributes"]}
    assert decision.denial_reason == "condition_failed"


def test_evaluate_detailed_reports_only_matching_action_resource_type_policies_as_evaluated_candidates():
    policies = [
        _policy(["users:read_own"], name="self_service"),
        _policy(["users:list_all"], name="user_management"),
    ]

    decision = PolicyEvaluationEngine.evaluate_detailed(
        policies, "users:list_all", "users", "admin@example.com"
    )

    assert decision.matched_policies == ["user_management"]
    assert "self_service" not in decision.matched_policies
    assert "self_service" not in decision.rejected_policies
    # evaluated_policies is the superset: every policy the user held,
    # including ones that never even matched action/resource_type
    assert decision.evaluated_policies == ["self_service", "user_management"]


def test_evaluate_detailed_denial_reason_is_no_matching_policy_when_nothing_matches_action():
    policies = [_policy(["users:read_own"], name="self_service")]

    decision = PolicyEvaluationEngine.evaluate_detailed(
        policies, "users:list_all", "users", "user@example.com"
    )

    assert decision.allowed is False
    assert decision.rejected_policies == []
    assert decision.denial_reason == "no_matching_policy"


def test_evaluate_reuses_evaluate_detailed_and_agrees_with_it():
    # evaluate() is a thin wrapper: confirm it stays in lockstep with
    # evaluate_detailed's "allowed" field rather than drifting.
    policy = _policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}},
        name="publish_drafts",
    )

    for resource in ({"status": "draft"}, {"status": "published"}, None):
        assert PolicyEvaluationEngine.evaluate(
            [policy], "documents:publish", "documents", "editor@example.com", resource=resource
        ) == PolicyEvaluationEngine.evaluate_detailed(
            [policy], "documents:publish", "documents", "editor@example.com", resource=resource
        ).allowed
