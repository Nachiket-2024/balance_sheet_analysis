import traceback

from ....logging.logging_config import get_logger
from ..condition_handler import ConditionHandler

logger = get_logger(__name__)


class SecurityContextCondition(ConditionHandler):
    """{"device_trusted": true, ...}: every key must match
    context["security_context"] (a reserved sub-key, see
    request_context_builder.py), not the top-level context. No MFA/
    device-trust infra exists yet; this just checks whatever a future
    trust-signal layer populates there.

    Denies if security_context (or any listed key in it) is missing, or
    condition_value is malformed: an unset security signal must never be
    treated as satisfied by default.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            if not condition_value:
                return True
            security_context = (context or {}).get("security_context")
            if not security_context:
                return False
            for key, expected_value in condition_value.items():
                if key not in security_context:
                    return False
                if security_context.get(key) != expected_value:
                    return False
            return True
        except Exception:
            logger.warning("security_context condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
