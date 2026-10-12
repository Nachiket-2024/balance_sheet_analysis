from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def resolve_current_datetime(context: dict | None, tz: ZoneInfo) -> datetime:
    """
    Returns the real wall clock in `tz`, unless `context` carries a
    "current_time" override (ISO 8601 string). This lets the authorization
    inspection endpoint simulate "would this be allowed at <time>?" and
    lets tests run time-based conditions deterministically. A naive
    override (no offset) is treated as UTC before converting.

    Raises ValueError on an invalid override string; callers should catch
    this and fail safe (deny).
    """
    override = (context or {}).get("current_time")
    if override:
        parsed = datetime.fromisoformat(override)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(tz)
    return datetime.now(tz)
