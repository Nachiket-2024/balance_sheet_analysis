# Unit coverage for SelfOnlyCondition, ResourceAttributesCondition, and
# ContextAttributesCondition (each tested in isolation, no DB, no evaluator),
# plus ConditionRegistry and ConditionEvaluationService's own dispatch/AND/
# fail-safe-on-unknown-key behavior. TimeCondition/DateRangeCondition live in
# test_policy_conditions_temporal_unit.py, NetworkCondition/
# SecurityContextCondition in test_policy_conditions_network_security_unit.py.
from backend.mystic_auth.authorization.conditions.condition_evaluation_service import (
    ConditionEvaluationService,
)
from backend.mystic_auth.authorization.conditions.condition_registry import (
    ConditionRegistry,
    default_condition_registry,
)
from backend.mystic_auth.authorization.conditions.condition_types.context_attributes_condition import (
    ContextAttributesCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.resource_attributes_condition import (
    ResourceAttributesCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.self_only_condition import (
    SelfOnlyCondition,
)

# ==================================================================
# SelfOnlyCondition
# ==================================================================

def test_self_only_allows_when_resource_belongs_to_caller():
    handler = SelfOnlyCondition()
    assert handler.evaluate(True, "user@example.com", {"email": "user@example.com"}, None) is True


def test_self_only_denies_when_resource_belongs_to_someone_else():
    handler = SelfOnlyCondition()
    assert handler.evaluate(True, "user@example.com", {"email": "other@example.com"}, None) is False


def test_self_only_denies_when_no_resource_supplied():
    handler = SelfOnlyCondition()
    assert handler.evaluate(True, "user@example.com", None, None) is False


def test_self_only_imposes_no_restriction_when_falsy():
    handler = SelfOnlyCondition()
    assert handler.evaluate(False, "user@example.com", None, None) is True


def test_self_only_fails_safe_on_resource_that_cannot_carry_email():
    """An exotic resource type (e.g. an object with no "email" attribute) must
    deny rather than raise, and a falsy user_email must never coincidentally
    match a resource with no owner email via None == None."""
    handler = SelfOnlyCondition()
    assert handler.evaluate(True, "user@example.com", object(), None) is False
    assert handler.evaluate(True, None, object(), None) is False
    assert handler.evaluate(True, "", {"email": ""}, None) is False


# ==================================================================
# ResourceAttributesCondition
# ==================================================================

def test_resource_attributes_allows_when_all_fields_match():
    handler = ResourceAttributesCondition()
    assert handler.evaluate({"status": "draft"}, "u@example.com", {"status": "draft"}, None) is True


def test_resource_attributes_denies_when_a_field_mismatches():
    handler = ResourceAttributesCondition()
    assert handler.evaluate({"status": "draft"}, "u@example.com", {"status": "published"}, None) is False


def test_resource_attributes_denies_when_no_resource_supplied():
    handler = ResourceAttributesCondition()
    assert handler.evaluate({"status": "draft"}, "u@example.com", None, None) is False


def test_resource_attributes_fails_safe_on_non_mapping_condition_value():
    """A malformed condition_value that bypassed the write-time validator (e.g. a
    direct DB write) must deny rather than raise when it's not a dict."""
    handler = ResourceAttributesCondition()
    assert handler.evaluate("not-a-dict", "u@example.com", {"status": "draft"}, None) is False
    assert handler.evaluate(["status", "draft"], "u@example.com", {"status": "draft"}, None) is False
    assert handler.evaluate(123, "u@example.com", {"status": "draft"}, None) is False


# ==================================================================
# ContextAttributesCondition
# ==================================================================

def test_context_attributes_allows_when_all_keys_match():
    handler = ContextAttributesCondition()
    assert handler.evaluate({"mfa_verified": True}, "u@example.com", None, {"mfa_verified": True}) is True


def test_context_attributes_denies_when_context_missing():
    handler = ContextAttributesCondition()
    assert handler.evaluate({"mfa_verified": True}, "u@example.com", None, None) is False


def test_context_attributes_fails_safe_on_non_mapping_condition_value():
    """A malformed condition_value that bypassed the write-time validator (e.g. a
    direct DB write) must deny rather than raise when it's not a dict."""
    handler = ContextAttributesCondition()
    assert handler.evaluate(["mfa_verified"], "u@example.com", None, {"mfa_verified": True}) is False
    assert handler.evaluate("mfa_verified", "u@example.com", None, {"mfa_verified": True}) is False


# ==================================================================
# ConditionRegistry
# ==================================================================

def test_default_registry_has_all_shipped_condition_types_registered():
    for key in ("self_only", "resource_attributes", "context_attributes", "time", "date_range", "network", "security_context"):
        assert default_condition_registry.get(key) is not None


def test_registry_returns_none_for_unregistered_key():
    registry = ConditionRegistry()
    assert registry.get("nonexistent") is None


# ==================================================================
# ConditionEvaluationService
# ==================================================================

def test_service_returns_true_for_empty_conditions():
    service = ConditionEvaluationService(default_condition_registry)
    assert service.evaluate(None, "u@example.com", None, None) is True
    assert service.evaluate({}, "u@example.com", None, None) is True


def test_service_ands_across_multiple_condition_keys():
    service = ConditionEvaluationService(default_condition_registry)
    conditions = {"self_only": True, "context_attributes": {"mfa_verified": True}}
    resource = {"email": "u@example.com"}

    allowed = service.evaluate(conditions, "u@example.com", resource, {"mfa_verified": True})
    denied_by_mfa = service.evaluate(conditions, "u@example.com", resource, {"mfa_verified": False})

    assert allowed is True
    assert denied_by_mfa is False


def test_service_fails_safe_when_conditions_is_not_a_mapping():
    """Policy.conditions is a JSONB column, so a direct DB write could put a
    non-dict value there. Evaluation must deny, not raise, on that."""
    service = ConditionEvaluationService(default_condition_registry)
    assert service.evaluate(["self_only"], "u@example.com", None, None) is False
    assert service.evaluate("self_only", "u@example.com", None, None) is False
    assert service.evaluate(123, "u@example.com", None, None) is False


def test_service_fails_safe_on_unrecognized_condition_key():
    """An unknown/typo'd condition key must deny, not be silently ignored:
    an unenforceable restriction must never count as satisfied."""
    service = ConditionEvaluationService(default_condition_registry)
    assert service.evaluate({"totally_made_up_condition": True}, "u@example.com", None, None) is False
