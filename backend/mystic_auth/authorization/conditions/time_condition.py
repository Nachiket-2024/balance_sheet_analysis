from datetime import time as dt_time
from zoneinfo import ZoneInfo

from .clock import resolve_current_datetime
from .condition_handler import ConditionHandler


class TimeCondition(ConditionHandler):
    """
    "time": {"start": "09:00", "end": "17:00", "timezone": "Australia/Sydney"}:
    the current wall-clock time, evaluated in the given timezone
    (default UTC if omitted), must fall within [start, end].

    Supports overnight ranges where start > end (e.g. "22:00"-"06:00"):
    interpreted as wrapping past midnight, so the allowed window is
    [start, 23:59:59] union [00:00, end] rather than an always-false empty
    range.

    Fails safe (denies) if start/end are missing, either isn't a valid
    "HH:MM" time, or the timezone name is invalid, per claude.md's
    "invalid context fails safely".
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
            return False
