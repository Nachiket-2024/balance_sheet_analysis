import traceback
from datetime import date
from zoneinfo import ZoneInfo

from ....logging.logging_config import get_logger
from ..clock import resolve_current_datetime
from ..condition_handler import ConditionHandler

logger = get_logger(__name__)


class DateRangeCondition(ConditionHandler):
    """
    "date_range": {"start": "2026-01-01", "end": "2026-03-01"}: "start"
    and "end" (ISO "YYYY-MM-DD") are this condition's one canonical, only
    supported field names (see conditions/condition_validator.py, which
    rejects anything else, e.g. "start_date"/"end_date", before a policy
    using them is ever stored; no aliases are supported). The current date
    (UTC, unless overridden, see clock.resolve_current_datetime) must fall
    within [start, end], inclusive. Used for temporary/contractor access
    windows and expiring permissions.

    Exactly one bound may be omitted for an open-ended range (only a start
    -> "access from this date on"; only an end -> "access until this
    date"). Fails safe (denies) if neither bound is present at all: a
    "date_range" condition with no recognizable bound (e.g. a legacy/typo'd
    field name that isn't "start"/"end") must never be treated as
    unconstrained, or if a supplied bound isn't a valid ISO date.
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
            # Fails safe (see class docstring): a malformed condition value
            # (bad ISO date, etc.) denies rather than raising, but logged so
            # a misconfigured policy doesn't silently deny forever with no
            # trail an operator can find.
            logger.warning("date_range condition failed to evaluate, denying:\n%s", traceback.format_exc())
            return False
