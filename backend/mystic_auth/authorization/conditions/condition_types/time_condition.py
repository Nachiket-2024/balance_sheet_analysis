import traceback
from datetime import time as dt_time
from zoneinfo import ZoneInfo

from ....logging.logging_config import get_logger
from ..clock import resolve_current_datetime
from ..condition_handler import ConditionHandler

logger = get_logger(__name__)


class TimeCondition(ConditionHandler):
    """{"start": "09:00", "end": "17:00", "timezone": "Australia/Sydney"}:
    current wall-clock time in the given timezone (UTC if omitted) must
    fall within [start, end].

    Supports overnight ranges where start > end (e.g. "22:00"-"06:00"),
    wrapping past midnight rather than being an always-false empty range.

    Denies if start/end are missing or invalid, or the timezone is invalid.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            start_str = condition_value.get("start")
            end_str = condition_value.get("end")
            if not start_str or not end_str:
                return False

            tz = ZoneInfo(condition_value.get("timezone") or "UTC")
            start = dt_time.fromisoformat(start_str)
            end = dt_time.fromisoformat(end_str)
            current = resolve_current_datetime(context, tz).time()

            if start <= end:
                return start <= current <= end
            # Overnight range: wraps past midnight
            return current >= start or current <= end
        except Exception:
            # Logged so a misconfigured policy's silent denial is traceable.
            logger.warning("time condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
