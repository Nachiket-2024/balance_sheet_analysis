import traceback
from datetime import date
from zoneinfo import ZoneInfo

from ....logging.logging_config import get_logger
from ..clock import resolve_current_datetime
from ..condition_handler import ConditionHandler

logger = get_logger(__name__)


class DateRangeCondition(ConditionHandler):
    """{"start": "2026-01-01", "end": "2026-03-01"}: current date (UTC
    unless overridden) must fall within [start, end] inclusive. Used for
    temporary access windows and expiring permissions. "start"/"end" are
    the only field names accepted (condition_validator.py rejects
    aliases like "start_date").

    One bound may be omitted for an open-ended range. Denies if neither
    bound is present (an unrecognized field name must never read as
    unconstrained) or a bound isn't a valid ISO date.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            start_str = condition_value.get("start")
            end_str = condition_value.get("end")
            if start_str is None and end_str is None:
                return False

            current_date = resolve_current_datetime(context, ZoneInfo("UTC")).date()

            if start_str and current_date < date.fromisoformat(start_str):
                return False
            return not (end_str and current_date > date.fromisoformat(end_str))
        except Exception:
            # Logged so a misconfigured policy's silent denial is traceable.
            logger.warning("date_range condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
