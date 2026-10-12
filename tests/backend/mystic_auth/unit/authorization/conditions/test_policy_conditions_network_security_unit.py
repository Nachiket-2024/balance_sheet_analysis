# Unit coverage for NetworkCondition and SecurityContextCondition, each
# handler tested in isolation (no DB, no evaluator).
from backend.mystic_auth.authorization.conditions.condition_types.network_condition import (
    NetworkCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.security_context_condition import (
    SecurityContextCondition,
)

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


def test_security_context_fails_safe_on_non_mapping_condition_value():
    """A malformed condition_value that bypassed the write-time validator
    must deny rather than raise AttributeError out of .items()."""
    handler = SecurityContextCondition()
    context = {"security_context": {"device_trusted": True}}
    assert handler.evaluate(["device_trusted"], "u@example.com", None, context) is False
    assert handler.evaluate(123, "u@example.com", None, context) is False
