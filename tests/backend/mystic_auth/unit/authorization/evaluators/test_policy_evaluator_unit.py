# Unit coverage for PolicyEvaluationEngine: the single place authorization
# decisions are computed. Pure and DB-free, so these tests build Policy objects
# directly rather than mocking a repository or database. Covers allow/deny
# decisions, ownership rules, resource attributes, and conditional policies.
#
# evaluate_detailed's explainability coverage (matched/rejected policies, denial
# reasons) is split out into test_policy_evaluator_detailed_unit.py.

from backend.mystic_auth.authorization.evaluators.policy_evaluator import (
    PolicyEvaluationEngine,
)
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
    # The evaluator trusts that only active policies were passed in (the repository
    # filters is_active=True first); it doesn't re-check is_active itself. A policy
    # marked is_active=False is still evaluated as a grant here.
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
    # An ownership condition with nothing to check ownership against cannot be
    # assumed satisfied: default-deny applies.
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
    resource = {"status": "published", "team_id": 5}

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
    # Both conditions must pass: ownership and a resource-state check.
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
        ["users:deactivate_any"],
        conditions={"context_attributes": {"mfa_verified": True}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "users:deactivate_any", "users", "admin@example.com", context={"mfa_verified": True}
    ) is True


def test_context_attributes_condition_denies_when_context_mismatches():
    policies = [_policy(
        ["users:deactivate_any"],
        conditions={"context_attributes": {"mfa_verified": True}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "users:deactivate_any", "users", "admin@example.com", context={"mfa_verified": False}
    ) is False


def test_context_attributes_condition_denies_when_no_context_is_supplied():
    policies = [_policy(
        ["users:deactivate_any"],
        conditions={"context_attributes": {"mfa_verified": True}},
    )]

    assert PolicyEvaluationEngine.evaluate(
        policies, "users:deactivate_any", "users", "admin@example.com", context=None
    ) is False


# ---------------------------- Roles do not enter the decision at all ----------------------------

def test_evaluation_never_references_role_two_role_free_policy_sets_differ_correctly():
    # There is no "role" concept in Policy or the evaluator's signature:
    # authorization is entirely a function of assigned policies.
    admin_like_policies = [_policy(["users:list_all", "users:update_any"])]
    plain_policies = [_policy(["users:read_own"])]

    assert PolicyEvaluationEngine.evaluate(
        admin_like_policies, "users:list_all", "users", "whoever@example.com"
    ) is True
    assert PolicyEvaluationEngine.evaluate(
        plain_policies, "users:list_all", "users", "whoever@example.com"
    ) is False
