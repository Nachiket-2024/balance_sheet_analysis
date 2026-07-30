# tests/backend/mystic_auth/unit/test_policy_evaluator_unit.py
#
# Unit coverage for PolicyEvaluationEngine : the single place authorization
# decisions are actually computed. Pure and DB-free, so these tests build
# Policy objects directly rather than mocking a repository or database.
#
# Per claude.md's Testing Requirements, these tests must prove: allow
# decisions, deny decisions, ownership rules, resource attributes,
# conditional policies, and (together with test_current_user_handler and
# test_authorization_service) that identical roles/no-role users can have
# different authorization outcomes.

from backend.mystic_auth.authorization.evaluators.policy_evaluator import PolicyEvaluationEngine
from backend.mystic_auth.authorization.models.policy_model import Policy


def _policy(actions, resource_type="users", conditions=None, name=None):
    return Policy(
        name=name, actions=actions, resource_type=resource_type, conditions=conditions, is_active=True
    )


# ---------------------------- Basic allow / deny ----------------------------

def test_allows_when_a_policy_grants_the_action_and_resource_type():
    policies = [_policy(["users:list_all"])]

    assert PolicyEvaluationEngine.evaluate(policies, "users:list_all", "users", "admin@example.com") is True


def test_denies_when_no_policy_is_assigned_at_all():
    assert PolicyEvaluationEngine.evaluate([], "users:list_all", "users", "user@example.com") is False


def test_denies_when_policies_exist_but_none_grant_this_action():
    policies = [_policy(["users:read_own", "users:update_own"])]

    assert PolicyEvaluationEngine.evaluate(policies, "users:list_all", "users", "user@example.com") is False


def test_denies_when_resource_type_does_not_match():
    policies = [_policy(["projects:read"], resource_type="projects")]

    assert PolicyEvaluationEngine.evaluate(policies, "projects:read", "documents", "user@example.com") is False


def test_wildcard_resource_type_matches_any_resource():
    policies = [_policy(["audit:read"], resource_type="*")]

    assert PolicyEvaluationEngine.evaluate(policies, "audit:read", "users", "auditor@example.com") is True
    assert PolicyEvaluationEngine.evaluate(policies, "audit:read", "projects", "auditor@example.com") is True


# ---------------------------- Multiple policies (OR semantics) ----------------------------

def test_grants_access_if_any_one_of_several_policies_allows():
    policies = [
        _policy(["users:read_own"]),
        _policy(["users:list_all"]),
    ]

    assert PolicyEvaluationEngine.evaluate(policies, "users:list_all", "users", "user@example.com") is True


def test_inactive_policy_state_is_the_repositorys_responsibility_not_the_evaluators():
    # The evaluator trusts that only active policies were passed in (the
    # repository filters is_active=True before evaluation) : it doesn't
    # re-check is_active itself. Confirm a policy explicitly marked
    # is_active=False is still evaluated as a grant here, since re-checking
    # would be dead logic duplicating the repository's filter.
    policy = _policy(["users:list_all"])
    policy.is_active = False

    assert PolicyEvaluationEngine.evaluate([policy], "users:list_all", "users", "user@example.com") is True


# ---------------------------- Conditions: ownership ("self_only") ----------------------------

def test_self_only_condition_allows_when_resource_belongs_to_caller():
    policies = [_policy(["documents:read"], resource_type="documents", conditions={"self_only": True})]
    resource = {"email": "user@example.com"}

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:read", "documents", "user@example.com", resource=resource
    ) is True


def test_self_only_condition_denies_when_resource_belongs_to_someone_else():
    policies = [_policy(["documents:read"], resource_type="documents", conditions={"self_only": True})]
    resource = {"email": "someone-else@example.com"}

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:read", "documents", "user@example.com", resource=resource
    ) is False


def test_self_only_condition_denies_when_no_resource_is_supplied():
    # An ownership condition with nothing to check ownership against cannot
    # be assumed satisfied : default-deny applies.
    policies = [_policy(["documents:read"], resource_type="documents", conditions={"self_only": True})]

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:read", "documents", "user@example.com", resource=None
    ) is False


def test_self_only_condition_works_against_an_attribute_bearing_object_not_just_a_dict():
    class _Resource:
        def __init__(self, email):
            self.email = email

    policies = [_policy(["documents:read"], resource_type="documents", conditions={"self_only": True})]

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:read", "documents", "user@example.com", resource=_Resource("user@example.com")
    ) is True
    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:read", "documents", "user@example.com", resource=_Resource("other@example.com")
    ) is False


def test_no_conditions_means_unconditional_grant():
    policies = [_policy(["users:update_any"], conditions=None)]

    assert PolicyEvaluationEngine.evaluate(
        policies, "users:update_any", "users", "admin@example.com", resource={"email": "anyone@example.com"}
    ) is True


# ---------------------------- Conditions: resource attributes ----------------------------

def test_resource_attributes_condition_allows_when_all_fields_match():
    policies = [_policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"resource_attributes": {"status": "draft", "team_id": 5}},
    )]
    resource = {"status": "draft", "team_id": 5}

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=resource
    ) is True


def test_resource_attributes_condition_denies_when_any_field_mismatches():
    policies = [_policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"resource_attributes": {"status": "draft", "team_id": 5}},
    )]
    resource = {"status": "published", "team_id": 5}  # status doesn't match

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=resource
    ) is False


def test_resource_attributes_condition_denies_when_no_resource_is_supplied():
    policies = [_policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=None
    ) is False


def test_resource_attributes_condition_works_against_an_attribute_bearing_object():
    class _Resource:
        def __init__(self, status):
            self.status = status

    policies = [_policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"resource_attributes": {"status": "draft"}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=_Resource("draft")
    ) is True
    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=_Resource("published")
    ) is False


def test_resource_attributes_and_self_only_can_be_combined():
    # Both conditions must pass : ownership AND a resource-state check.
    policies = [_policy(
        ["documents:publish"],
        resource_type="documents",
        conditions={"self_only": True, "resource_attributes": {"status": "draft"}},
    )]

    owned_and_draft = {"email": "editor@example.com", "status": "draft"}
    owned_but_published = {"email": "editor@example.com", "status": "published"}
    not_owned_but_draft = {"email": "someone-else@example.com", "status": "draft"}

    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=owned_and_draft
    ) is True
    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=owned_but_published
    ) is False
    assert PolicyEvaluationEngine.evaluate(
        policies, "documents:publish", "documents", "editor@example.com", resource=not_owned_but_draft
    ) is False


# ---------------------------- Conditions: contextual information ----------------------------

def test_context_attributes_condition_allows_when_context_matches():
    policies = [_policy(
        ["users:delete_any"],
        conditions={"context_attributes": {"mfa_verified": True}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "users:delete_any", "users", "admin@example.com", context={"mfa_verified": True}
    ) is True


def test_context_attributes_condition_denies_when_context_mismatches():
    policies = [_policy(
        ["users:delete_any"],
        conditions={"context_attributes": {"mfa_verified": True}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "users:delete_any", "users", "admin@example.com", context={"mfa_verified": False}
    ) is False


def test_context_attributes_condition_denies_when_no_context_is_supplied():
    policies = [_policy(
        ["users:delete_any"],
        conditions={"context_attributes": {"mfa_verified": True}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "users:delete_any", "users", "admin@example.com", context=None
    ) is False


# ---------------------------- Roles do not enter the decision at all ----------------------------

def test_evaluation_never_references_role_two_role_free_policy_sets_differ_correctly():
    # There is no "role" concept anywhere in Policy or the evaluator's
    # signature : authorization is 100% a function of assigned policies.
    admin_like_policies = [_policy(["users:list_all", "users:update_any"])]
    plain_policies = [_policy(["users:read_own"])]

    assert PolicyEvaluationEngine.evaluate(
        admin_like_policies, "users:list_all", "users", "whoever@example.com"
    ) is True
    assert PolicyEvaluationEngine.evaluate(
        plain_policies, "users:list_all", "users", "whoever@example.com"
    ) is False


# ---------------------------- evaluate_detailed (explainability) ----------------------------
# evaluate_detailed now returns an AuthorizationDecision (see
# evaluators/authorization_decision.py) rather than a bare dict : per
# claude.md's Authorization Decision Explainability, "detailed APIs should
# use new structure". matched_policies/rejected_policies replace the old
# granting_policy_names/"candidate minus granting" split.

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
    # This is the whole point of evaluate_detailed over evaluate: telling
    # apart "no policy even applies" from "a policy applies but its
    # conditions rejected this specific resource" : and now, which
    # condition key specifically failed.
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
        _policy(["users:list_all"], name="user_administration"),
    ]

    decision = PolicyEvaluationEngine.evaluate_detailed(
        policies, "users:list_all", "users", "admin@example.com"
    )

    assert decision.matched_policies == ["user_administration"]
    assert "self_service" not in decision.matched_policies
    assert "self_service" not in decision.rejected_policies
    # evaluated_policies is the superset: every policy the user held,
    # including ones that never even matched action/resource_type
    assert decision.evaluated_policies == ["self_service", "user_administration"]


def test_evaluate_detailed_denial_reason_is_no_matching_policy_when_nothing_matches_action():
    policies = [_policy(["users:read_own"], name="self_service")]

    decision = PolicyEvaluationEngine.evaluate_detailed(
        policies, "users:list_all", "users", "user@example.com"
    )

    assert decision.allowed is False
    assert decision.rejected_policies == []
    assert decision.denial_reason == "no_matching_policy"


def test_evaluate_reuses_evaluate_detailed_and_agrees_with_it():
    # evaluate() is now a thin wrapper : confirm it stays in lockstep with
    # evaluate_detailed's own "allowed" field rather than drifting.
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
