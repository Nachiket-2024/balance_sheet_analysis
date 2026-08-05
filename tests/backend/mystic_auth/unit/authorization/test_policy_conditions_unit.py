# tests/backend/mystic_auth/unit/test_policy_conditions_unit.py
#
# Unit coverage for the modular condition framework (the advanced
# Policy Conditions"): Authorization Engine -> Condition Evaluation Service
# -> Condition Handlers. Each handler is tested in isolation (no DB, no
# evaluator), plus the service's dispatch/AND/fail-safe-on-unknown-key
# behavior, plus the registry itself.
from backend.mystic_auth.authorization.conditions.condition_evaluation_service import ConditionEvaluationService
from backend.mystic_auth.authorization.conditions.condition_registry import (
    ConditionRegistry,
    default_condition_registry,
)
from backend.mystic_auth.authorization.conditions.condition_types.context_attributes_condition import (
    ContextAttributesCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.date_range_condition import DateRangeCondition
from backend.mystic_auth.authorization.conditions.condition_types.network_condition import NetworkCondition
from backend.mystic_auth.authorization.conditions.condition_types.resource_attributes_condition import (
    ResourceAttributesCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.security_context_condition import (
    SecurityContextCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.self_only_condition import SelfOnlyCondition
from backend.mystic_auth.authorization.conditions.condition_types.time_condition import TimeCondition

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


# ==================================================================
# ContextAttributesCondition
# ==================================================================

def test_context_attributes_allows_when_all_keys_match():
    handler = ContextAttributesCondition()
    assert handler.evaluate({"mfa_verified": True}, "u@example.com", None, {"mfa_verified": True}) is True


def test_context_attributes_denies_when_context_missing():
    handler = ContextAttributesCondition()
    assert handler.evaluate({"mfa_verified": True}, "u@example.com", None, None) is False


# ==================================================================
# TimeCondition
# ==================================================================

def test_time_allows_within_business_hours():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00", "timezone": "UTC"}
    context = {"current_time": "2026-07-13T12:00:00+00:00"}
    assert handler.evaluate(condition, "u@example.com", None, context) is True


def test_time_denies_outside_business_hours():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00", "timezone": "UTC"}
    context = {"current_time": "2026-07-13T20:00:00+00:00"}
    assert handler.evaluate(condition, "u@example.com", None, context) is False


def test_time_handles_overnight_range_wrapping_midnight():
    handler = TimeCondition()
    condition = {"start": "22:00", "end": "06:00", "timezone": "UTC"}
    # 23:30 is within the overnight window (after 22:00)
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T23:30:00+00:00"}) is True
    # 03:00 is within the overnight window (before 06:00)
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-14T03:00:00+00:00"}) is True
    # 12:00 (midday) is outside the overnight window
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T12:00:00+00:00"}) is False


def test_time_respects_timezone_conversion():
    handler = TimeCondition()
    # 09:00 Sydney (UTC+10 in July, standard time) == 23:00 UTC the prior day
    condition = {"start": "09:00", "end": "17:00", "timezone": "Australia/Sydney"}
    context = {"current_time": "2026-07-13T23:30:00+00:00"}
    assert handler.evaluate(condition, "u@example.com", None, context) is True


def test_time_defaults_to_utc_when_timezone_omitted():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T12:00:00+00:00"}) is True


def test_time_fails_safe_on_invalid_timezone():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00", "timezone": "Not/A_Real_Zone"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T12:00:00+00:00"}) is False


def test_time_fails_safe_on_missing_start_or_end():
    handler = TimeCondition()
    assert handler.evaluate({"end": "17:00"}, "u@example.com", None, {}) is False
    assert handler.evaluate({"start": "09:00"}, "u@example.com", None, {}) is False


def test_time_fails_safe_on_malformed_time_string():
    handler = TimeCondition()
    condition = {"start": "not-a-time", "end": "17:00"}
    assert handler.evaluate(condition, "u@example.com", None, {}) is False


# ==================================================================
# DateRangeCondition
# ==================================================================

def test_date_range_allows_within_range():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-02-01T00:00:00+00:00"}) is True


def test_date_range_denies_before_start():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2025-12-31T00:00:00+00:00"}) is False


def test_date_range_denies_after_end():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-03-02T00:00:00+00:00"}) is False


def test_date_range_allows_boundary_dates_inclusive():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-01-01T00:00:00+00:00"}) is True
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-03-01T23:59:00+00:00"}) is True


def test_date_range_open_ended_start_only():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2099-01-01T00:00:00+00:00"}) is True


def test_date_range_open_ended_end_only():
    handler = DateRangeCondition()
    condition = {"end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2000-01-01T00:00:00+00:00"}) is True


def test_date_range_fails_safe_on_malformed_date():
    handler = DateRangeCondition()
    condition = {"start": "not-a-date"}
    assert handler.evaluate(condition, "u@example.com", None, {}) is False


def test_date_range_fails_safe_when_neither_bound_present():
    """Regression: a date_range condition with no recognizable "start" or
    "end" (empty dict, or wrong field names like "start_date"/"end_date")
    must deny : never silently treated as an unconstrained/always-allow
    range. condition_validator.py already blocks this at write time; this
    pins the evaluator's own independent fail-safe (defense in depth)."""
    handler = DateRangeCondition()
    assert handler.evaluate({}, "u@example.com", None, {}) is False
    assert handler.evaluate(
        {"start_date": "2026-01-01", "end_date": "2026-03-01"}, "u@example.com", None, {}
    ) is False


# ==================================================================
# NetworkCondition
# ==================================================================

def test_network_allows_exact_ip_match():
    handler = NetworkCondition()
    condition = {"allowed_ips": ["203.0.113.7"]}
    assert handler.evaluate(condition, "u@example.com", None, {"ip_address": "203.0.113.7"}) is True


def test_network_allows_ip_within_cidr_range():
    handler = NetworkCondition()
    condition = {"allowed_ips": ["10.0.0.0/8"]}
    assert handler.evaluate(condition, "u@example.com", None, {"ip_address": "10.1.2.3"}) is True


def test_network_denies_ip_outside_allowed_ranges():
    handler = NetworkCondition()
    condition = {"allowed_ips": ["10.0.0.0/8"]}
    assert handler.evaluate(condition, "u@example.com", None, {"ip_address": "192.168.1.1"}) is False


def test_network_denies_when_context_has_no_ip():
    handler = NetworkCondition()
    condition = {"allowed_ips": ["10.0.0.0/8"]}
    assert handler.evaluate(condition, "u@example.com", None, {}) is False
    assert handler.evaluate(condition, "u@example.com", None, None) is False


def test_network_fails_safe_on_invalid_ip_string():
    handler = NetworkCondition()
    condition = {"allowed_ips": ["10.0.0.0/8"]}
    assert handler.evaluate(condition, "u@example.com", None, {"ip_address": "not-an-ip"}) is False


def test_network_denies_when_allowed_ips_empty():
    handler = NetworkCondition()
    assert handler.evaluate({"allowed_ips": []}, "u@example.com", None, {"ip_address": "10.0.0.1"}) is False


# ==================================================================
# SecurityContextCondition
# ==================================================================

def test_security_context_allows_when_all_fields_match():
    handler = SecurityContextCondition()
    condition = {"device_trusted": True}
    context = {"security_context": {"device_trusted": True}}
    assert handler.evaluate(condition, "u@example.com", None, context) is True


def test_security_context_denies_on_mismatch():
    handler = SecurityContextCondition()
    condition = {"assurance_level": "high"}
    context = {"security_context": {"assurance_level": "low"}}
    assert handler.evaluate(condition, "u@example.com", None, context) is False


def test_security_context_denies_when_context_missing_entirely():
    handler = SecurityContextCondition()
    assert handler.evaluate({"device_trusted": True}, "u@example.com", None, None) is False


def test_security_context_denies_when_security_context_subkey_missing():
    handler = SecurityContextCondition()
    assert handler.evaluate({"device_trusted": True}, "u@example.com", None, {"ip_address": "1.2.3.4"}) is False


def test_security_context_denies_when_key_absent_from_security_context():
    handler = SecurityContextCondition()
    context = {"security_context": {"other_field": 1}}
    assert handler.evaluate({"device_trusted": True}, "u@example.com", None, context) is False


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


def test_service_fails_safe_on_unrecognized_condition_key():
    """An unknown/typo'd condition key must deny rather than be silently
    ignored : an unenforceable restriction must never be treated as
    satisfied."""
    service = ConditionEvaluationService(default_condition_registry)
    assert service.evaluate({"totally_made_up_condition": True}, "u@example.com", None, None) is False
