import traceback

from ....logging.logging_config import get_logger
from ..condition_handler import ConditionHandler
from ..resource_field import get_field

logger = get_logger(__name__)


class SelfOnlyCondition(ConditionHandler):
    """"self_only": true requires the resource's "email" field to match
    the acting user's email. Falsy value means no restriction; no
    resource means deny. Both emails are checked for truthiness before
    comparing so two missing emails (None == None) can't be mistaken for
    a match."""

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            if not condition_value:
                return True
            if resource is None:
                return False
            owner_email = get_field(resource, "email")
            if not owner_email or not user_email:
                return False
            return owner_email == user_email
        except Exception:
            logger.warning("self_only condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
