# tests/backend/mystic_auth/unit/test_condition_validator_unit.py
#
# Unit coverage for validate_conditions (claude.md's "Policy Condition
# Validation"): invalid policies must be rejected before storage: unknown
# keys, wrong types, missing required fields, invalid timezone/IP/dates.
import pytest
from backend.mystic_auth.authorization.conditions.condition_validator import (
    ConditionValidationError,
    validate_conditions,
)


def _errors(conditions) -> list[str]:
    with pytest.raises(ConditionValidationError) as exc_info:
        validate_conditions(conditions)
    return exc_info.value.errors


# ---------------------------- Top-level shape ----------------------------

def test_none_conditions_is_valid():
    validate_conditions(None)  # must not raise


def test_conditions_must_be_an_object():
    errors = _errors("not-a-dict")
    assert any("JSON object" in e for e in errors)


def test_unknown_condition_key_is_rejected():
    errors = _errors({"totally_made_up": True})
    assert any("Unknown condition key" in e for e in errors)


def test_multiple_errors_are_all_collected_not_just_the_first():
    errors = _errors({"totally_made_up": True, "time": "not-an-object"})
    assert len(errors) == 2


# ---------------------------- self_only ----------------------------

def test_self_only_valid():
    validate_conditions({"self_only": True})


def test_self_only_rejects_non_boolean():
    errors = _errors({"self_only": "yes"})
    assert any("self_only" in e for e in errors)


# ---------------------------- resource_attributes / context_attributes / security_context ----------------------------

def test_resource_attributes_valid():
    validate_conditions({"resource_attributes": {"status": "active"}})


def test_resource_attributes_rejects_empty_object():
    errors = _errors({"resource_attributes": {}})
    assert any("resource_attributes" in e for e in errors)


def test_context_attributes_valid():
    validate_conditions({"context_attributes": {"department": "finance"}})


def test_context_attributes_rejects_non_dict():
    errors = _errors({"context_attributes": ["finance"]})
    assert any("context_attributes" in e for e in errors)


def test_security_context_valid():
    validate_conditions({"security_context": {"device_trusted": True}})


def test_security_context_rejects_empty_object():
    errors = _errors({"security_context": {}})
    assert any("security_context" in e for e in errors)


# ---------------------------- time ----------------------------

def test_time_valid_with_timezone():
    validate_conditions({"time": {"start": "09:00", "end": "17:00", "timezone": "UTC"}})


def test_time_valid_without_timezone():
    validate_conditions({"time": {"start": "09:00", "end": "17:00"}})


def test_time_rejects_non_object():
    errors = _errors({"time": "09:00-17:00"})
    assert any("'time' must be an object" in e for e in errors)


def test_time_rejects_missing_start_and_end():
    errors = _errors({"time": {}})
    assert any("time.start" in e for e in errors)
    assert any("time.end" in e for e in errors)


def test_time_rejects_malformed_time_string():
    errors = _errors({"time": {"start": "not-a-time", "end": "17:00"}})
    assert any("time.start" in e for e in errors)


def test_time_rejects_invalid_timezone():
    errors = _errors({"time": {"start": "09:00", "end": "17:00", "timezone": "Not/A_Zone"}})
    assert any("timezone" in e for e in errors)


# ---------------------------- date_range ----------------------------

def test_date_range_valid_both_bounds():
    validate_conditions({"date_range": {"start": "2026-01-01", "end": "2026-03-01"}})


def test_date_range_valid_open_ended():
    validate_conditions({"date_range": {"start": "2026-01-01"}})
    validate_conditions({"date_range": {"end": "2026-03-01"}})


def test_date_range_rejects_neither_bound_present():
    errors = _errors({"date_range": {}})
    assert any("at least one of" in e for e in errors)


def test_date_range_rejects_malformed_date():
    errors = _errors({"date_range": {"start": "not-a-date"}})
    assert any("date_range.start" in e for e in errors)


def test_date_range_canonical_field_names_are_start_and_end_only():
    """Regression pin: "start"/"end" are date_range's one canonical,
    documented shape (matching "time"'s own start/end naming), no
    aliases like "start_date"/"end_date" are recognized. A dict using
    those names has neither "start" nor "end" from this validator's point
    of view, so it must be rejected exactly like an empty dict."""
    errors = _errors({"date_range": {"start_date": "2026-01-01", "end_date": "2026-03-01"}})
    assert any("at least one of" in e for e in errors)


# ---------------------------- network ----------------------------

def test_network_valid_single_ip_and_cidr():
    validate_conditions({"network": {"allowed_ips": ["203.0.113.7", "10.0.0.0/24"]}})


def test_network_rejects_empty_allowed_ips():
    errors = _errors({"network": {"allowed_ips": []}})
    assert any("allowed_ips" in e for e in errors)


def test_network_rejects_missing_allowed_ips():
    errors = _errors({"network": {}})
    assert any("allowed_ips" in e for e in errors)


def test_network_rejects_invalid_ip():
    errors = _errors({"network": {"allowed_ips": ["not-an-ip"]}})
    assert any("invalid IP/CIDR" in e for e in errors)


def test_network_rejects_invalid_cidr():
    errors = _errors({"network": {"allowed_ips": ["10.0.0.0/99"]}})
    assert any("invalid IP/CIDR" in e for e in errors)
