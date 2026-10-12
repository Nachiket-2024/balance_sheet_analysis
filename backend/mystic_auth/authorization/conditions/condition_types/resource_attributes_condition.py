import traceback

from ....logging.logging_config import get_logger
from ..condition_handler import ConditionHandler
from ..resource_field import get_field

logger = get_logger(__name__)


class ResourceAttributesCondition(ConditionHandler):
    """{field: expected_value, ...}: every field must match the actual
    resource (e.g. {"status": "published"}). Empty map means no
    restriction; missing resource denies. Denies on a malformed
    condition_value too (defense in depth against bypassing
    condition_validator.py)."""

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            if not condition_value:
                return True
            if resource is None:
                return False
            return all(
                get_field(resource, field) == expected_value for field, expected_value in condition_value.items()
            )
        except Exception:
            logger.warning("resource_attributes condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
