from ..condition_handler import ConditionHandler
from ..resource_field import get_field


class ResourceAttributesCondition(ConditionHandler):
    """
    "resource_attributes": {field: expected_value, ...}: every listed
    field must equal its expected value on the actual resource (e.g.
    {"status": "published"} for a resource-state-scoped grant). An empty/
    missing map imposes no restriction. Unsatisfiable if no resource was
    supplied.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        if not condition_value:
            return True
        if resource is None:
            return False
        return all(get_field(resource, field) == expected_value for field, expected_value in condition_value.items())
