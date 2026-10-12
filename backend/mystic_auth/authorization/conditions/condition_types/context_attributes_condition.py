import traceback

from ....logging.logging_config import get_logger
from ..condition_handler import ConditionHandler

logger = get_logger(__name__)


class ContextAttributesCondition(ConditionHandler):
    """{key: expected_value, ...}: every key must match the caller-supplied
    context (e.g. {"mfa_verified": True}). Empty map means no restriction;
    missing context denies. Denies on a malformed condition_value too
    (defense in depth against bypassing condition_validator.py)."""

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            if not condition_value:
                return True
            if context is None:
                return False
            return all(context.get(key) == expected_value for key, expected_value in condition_value.items())
        except Exception:
            logger.warning("context_attributes condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
