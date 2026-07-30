from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def resolve_current_datetime(context: dict | None, tz: ZoneInfo) -> datetime:
    """
    Returns the real wall clock in `tz`, unless `context` carries a
    "current_time" override (ISO 8601 string): this is what lets the
    authorization-check inspection endpoint answer "would this be allowed
    at <hypothetical time>?", and lets tests exercise time/date-range
    conditions deterministically without patching the system clock. A
    naive override (no offset) is treated as UTC before converting.

    Raises ValueError if "current_time" is present but not a valid ISO
    8601 datetime string: callers (ConditionHandlers) are expected to
    catch this and fail safe (deny).
    """
    override = (context or {}).get("current_time")
    if override:
        parsed = datetime.fromisoformat(override)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(tz)
    return datetime.now(tz)
