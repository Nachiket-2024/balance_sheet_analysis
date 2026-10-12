# Cross-checks that condition_validator.py (write-time) and the condition handlers
# (conditions/*.py, evaluation-time) agree on the same JSON shape per condition type.
# Each canonical payload below must pass validation and be understood correctly by
# its handler, not silently ignored.
from backend.mystic_auth.authorization.conditions.condition_handler import (
    ConditionHandler,
)
from backend.mystic_auth.authorization.conditions.condition_registry import (
    default_condition_registry,
    register_condition_type,
)
from backend.mystic_auth.authorization.conditions.condition_types.context_attributes_condition import (
    ContextAttributesCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.date_range_condition import (
    DateRangeCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.network_condition import (
    NetworkCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.resource_attributes_condition import (
    ResourceAttributesCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.security_context_condition import (
    SecurityContextCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.self_only_condition import (
    SelfOnlyCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.time_condition import (
    TimeCondition,
)
from backend.mystic_auth.authorization.conditions.condition_validator import (
    validate_conditions,
)


def test_self_only_canonical_shape_is_accepted_by_both_layers():
    payload = {"self_only": True}
    validate_conditions(payload)  # must not raise
    assert SelfOnlyCondition().evaluate(True, "u@example.com", {"email": "u@example.com"}, None) is True


def test_resource_attributes_canonical_shape_is_accepted_by_both_layers():
    payload = {"resource_attributes": {"status": "active"}}
    validate_conditions(payload)
    assert ResourceAttributesCondition().evaluate({"status": "active"}, "u@example.com", {"status": "active"}, None) is True


def test_context_attributes_canonical_shape_is_accepted_by_both_layers():
    payload = {"context_attributes": {"department": "finance"}}
    validate_conditions(payload)
    assert ContextAttributesCondition().evaluate({"department": "finance"}, "u@example.com", None, {"department": "finance"}) is True


def test_time_canonical_shape_is_accepted_by_both_layers():
    payload = {"time": {"start": "09:00", "end": "17:00", "timezone": "UTC"}}
    validate_conditions(payload)
    result = TimeCondition().evaluate(
        payload["time"], "u@example.com", None, {"current_time": "2026-07-13T12:00:00+00:00"}
    )
    assert result is True


def test_date_range_canonical_shape_is_accepted_by_both_layers():
    payload = {"date_range": {"start": "2026-01-01", "end": "2026-03-01"}}
    validate_conditions(payload)
    result = DateRangeCondition().evaluate(
        payload["date_range"], "u@example.com", None, {"current_time": "2026-02-01T00:00:00+00:00"}
    )
    assert result is True


def test_network_canonical_shape_is_accepted_by_both_layers():
    payload = {"network": {"allowed_ips": ["10.0.0.0/24"]}}
    validate_conditions(payload)
    result = NetworkCondition().evaluate(payload["network"], "u@example.com", None, {"ip_address": "10.0.0.5"})
    assert result is True


def test_security_context_canonical_shape_is_accepted_by_both_layers():
    payload = {"security_context": {"device_trusted": True}}
    validate_conditions(payload)
    result = SecurityContextCondition().evaluate(
        payload["security_context"], "u@example.com", None, {"security_context": {"device_trusted": True}}
    )
    assert result is True


def test_app_condition_registration_updates_validation_and_evaluation():
    class ProjectScopeCondition(ConditionHandler):
        def evaluate(self, condition_value, user_email, resource, context) -> bool:
            return (context or {}).get("project_id") == condition_value.get("project_id")

    def validate_project_scope(value) -> list[str]:
        if not isinstance(value, dict) or not isinstance(value.get("project_id"), str):
            return ["'project_scope_test.project_id' must be a string"]
        return []

    register_condition_type("project_scope_test", ProjectScopeCondition(), validate_project_scope)
    validate_conditions({"project_scope_test": {"project_id": "p1"}})

    handler = default_condition_registry.get("project_scope_test")
    assert handler is not None
    assert handler.evaluate({"project_id": "p1"}, "u@example.com", None, {"project_id": "p1"}) is True
    assert handler.evaluate({"project_id": "p1"}, "u@example.com", None, {"project_id": "p2"}) is False
