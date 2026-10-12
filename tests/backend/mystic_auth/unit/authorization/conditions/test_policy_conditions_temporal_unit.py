# Unit coverage for the temporal condition handlers (TimeCondition, DateRangeCondition).
from backend.mystic_auth.authorization.conditions.condition_types.date_range_condition import (
    DateRangeCondition,
)
from backend.mystic_auth.authorization.conditions.condition_types.time_condition import (
    TimeCondition,
)

# ==================================================================
# TimeCondition
# ==================================================================

def test_time_allows_within_business_hours():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00", "timezone": "UTC"}
    context = {"current_time": "2026-07-13T12:00:00+00:00"}
    assert handler.evaluate(condition, "u@example.com", None, context) is True


def test_time_denies_outside_business_hours():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00", "timezone": "UTC"}
    context = {"current_time": "2026-07-13T20:00:00+00:00"}
    assert handler.evaluate(condition, "u@example.com", None, context) is False


def test_time_handles_overnight_range_wrapping_midnight():
    handler = TimeCondition()
    condition = {"start": "22:00", "end": "06:00", "timezone": "UTC"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T23:30:00+00:00"}) is True
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-14T03:00:00+00:00"}) is True
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T12:00:00+00:00"}) is False


def test_time_respects_timezone_conversion():
    handler = TimeCondition()
    # 09:00 Sydney (UTC+10 in July) is 23:00 UTC the prior day
    condition = {"start": "09:00", "end": "17:00", "timezone": "Australia/Sydney"}
    context = {"current_time": "2026-07-13T23:30:00+00:00"}
    assert handler.evaluate(condition, "u@example.com", None, context) is True


def test_time_defaults_to_utc_when_timezone_omitted():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T12:00:00+00:00"}) is True


def test_time_fails_safe_on_invalid_timezone():
    handler = TimeCondition()
    condition = {"start": "09:00", "end": "17:00", "timezone": "Not/A_Real_Zone"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-07-13T12:00:00+00:00"}) is False


def test_time_fails_safe_on_missing_start_or_end():
    handler = TimeCondition()
    assert handler.evaluate({"end": "17:00"}, "u@example.com", None, {}) is False
    assert handler.evaluate({"start": "09:00"}, "u@example.com", None, {}) is False


def test_time_fails_safe_on_malformed_time_string():
    handler = TimeCondition()
    condition = {"start": "not-a-time", "end": "17:00"}
    assert handler.evaluate(condition, "u@example.com", None, {}) is False


# ==================================================================
# DateRangeCondition
# ==================================================================

def test_date_range_allows_within_range():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-02-01T00:00:00+00:00"}) is True


def test_date_range_denies_before_start():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2025-12-31T00:00:00+00:00"}) is False


def test_date_range_denies_after_end():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-03-02T00:00:00+00:00"}) is False


def test_date_range_allows_boundary_dates_inclusive():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01", "end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-01-01T00:00:00+00:00"}) is True
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2026-03-01T23:59:00+00:00"}) is True


def test_date_range_open_ended_start_only():
    handler = DateRangeCondition()
    condition = {"start": "2026-01-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2099-01-01T00:00:00+00:00"}) is True


def test_date_range_open_ended_end_only():
    handler = DateRangeCondition()
    condition = {"end": "2026-03-01"}
    assert handler.evaluate(condition, "u@example.com", None, {"current_time": "2000-01-01T00:00:00+00:00"}) is True


def test_date_range_fails_safe_on_malformed_date():
    handler = DateRangeCondition()
    condition = {"start": "not-a-date"}
    assert handler.evaluate(condition, "u@example.com", None, {}) is False


def test_date_range_fails_safe_when_neither_bound_present():
    """A date_range with no recognizable start/end must deny, not be treated
    as unconstrained. Fail-safe independent of condition_validator.py."""
    handler = DateRangeCondition()
    assert handler.evaluate({}, "u@example.com", None, {}) is False
    assert handler.evaluate(
        {"start_date": "2026-01-01", "end_date": "2026-03-01"}, "u@example.com", None, {}
    ) is False
