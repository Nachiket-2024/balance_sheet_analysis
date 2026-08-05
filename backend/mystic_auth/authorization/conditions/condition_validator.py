import ipaddress
from datetime import date
from datetime import time as dt_time
from zoneinfo import available_timezones


class ConditionValidationError(ValueError):
    """
    Raised by validate_conditions when a policy's `conditions` block is
    invalid. Carries every problem found (not just the first), so a caller
    creating/updating a policy with several mistakes gets one useful error
    response instead of having to fix issues one at a time.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


# Mirrors conditions/condition_registry.py's default_condition_registry,
# kept as its own explicit set (rather than importing the registry) so this
# validator's "which keys exist" list is a deliberate, reviewable contract,
# not implicitly whatever handlers happen to be registered.
_SUPPORTED_KEYS = frozenset(
    {
        "self_only",
        "resource_attributes",
        "context_attributes",
        "time",
        "date_range",
        "network",
        "security_context",
    }
)


def validate_conditions(conditions: dict | None) -> None:
    """
    Validates a policy's whole `conditions` block, exactly as it would be
    persisted. None/empty is valid (an unconditional grant).

    Raises:
        ConditionValidationError: if `conditions` isn't a JSON object, if
        it contains a key outside this app's supported vocabulary, or if
        any key's value fails that condition type's own shape/type/range
        checks (see the per-key validators below): collecting every
        problem found across the whole block, not just the first.

    Called from api/pbac_routes/policy_crud_routes.py's create_policy and update_policy
    *before* any database write ("Must happen before database
    writes"): an invalid conditions block must never be persisted. This
    is a write-time complement to ConditionEvaluationService's own
    fail-safe deny-on-unknown-key behavior at *evaluation* time (defense in
    depth): that runtime fail-safe protects against conditions that
    somehow got into the database another way (e.g. a direct migration/DB
    write); this validator's job is to stop bad data from ever reaching
    that point via the management API, with a clear error explaining why,
    rather than a policy silently never granting anything.
    """
    if conditions is None:
        return
    if not isinstance(conditions, dict):
        raise ConditionValidationError(["'conditions' must be a JSON object"])

    errors: list[str] = []
    for key, value in conditions.items():
        validator = _VALIDATORS.get(key)
        if validator is None:
            errors.append(f"Unknown condition key '{key}'")
            continue
        errors.extend(validator(value))

    if errors:
        raise ConditionValidationError(errors)


def _validate_self_only(value) -> list[str]:
    if not isinstance(value, bool):
        return ["'self_only' must be a boolean"]
    return []


def _validate_resource_attributes(value) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["'resource_attributes' must be a non-empty object"]
    return []


def _validate_context_attributes(value) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["'context_attributes' must be a non-empty object"]
    return []


def _validate_security_context(value) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["'security_context' must be a non-empty object"]
    return []


def _validate_time(value) -> list[str]:
    if not isinstance(value, dict):
        return ["'time' must be an object"]

    errors: list[str] = []
    for bound in ("start", "end"):
        raw = value.get(bound)
        if not isinstance(raw, str):
            errors.append(f"'time.{bound}' is required and must be a string ('HH:MM')")
            continue
        try:
            dt_time.fromisoformat(raw)
        except ValueError:
            errors.append(f"'time.{bound}' is not a valid time: {raw!r}")

    timezone_name = value.get("timezone")
    if timezone_name is not None and (
        not isinstance(timezone_name, str) or timezone_name not in available_timezones()
    ):
        errors.append(f"'time.timezone' is not a valid IANA timezone name: {timezone_name!r}")

    return errors


def _validate_date_range(value) -> list[str]:
    # Canonical, only-supported field names are "start"/"end" (matching
    # the "time" condition's own start/end naming), mirrored exactly by
    # DateRangeCondition.evaluate. No aliases (e.g. "start_date"/"end_date")
    # are recognized; a dict using them fails the "requires at least one
    # of" check below the same as an empty dict would.
    if not isinstance(value, dict):
        return ["'date_range' must be an object"]

    start = value.get("start")
    end = value.get("end")
    if start is None and end is None:
        return ["'date_range' requires at least one of 'start' or 'end'"]

    errors: list[str] = []
    for bound_name, bound_value in (("start", start), ("end", end)):
        if bound_value is None:
            continue
        if not isinstance(bound_value, str):
            errors.append(f"'date_range.{bound_name}' must be a string ('YYYY-MM-DD')")
            continue
        try:
            date.fromisoformat(bound_value)
        except ValueError:
            errors.append(f"'date_range.{bound_name}' is not a valid date: {bound_value!r}")

    return errors


def _validate_network(value) -> list[str]:
    if not isinstance(value, dict):
        return ["'network' must be an object"]

    allowed_ips = value.get("allowed_ips")
    if not isinstance(allowed_ips, list) or not allowed_ips:
        return ["'network.allowed_ips' must be a non-empty list"]

    errors: list[str] = []
    for entry in allowed_ips:
        if not isinstance(entry, str):
            errors.append(f"'network.allowed_ips' entries must be strings, got {entry!r}")
            continue
        try:
            if "/" in entry:
                ipaddress.ip_network(entry, strict=False)
            else:
                ipaddress.ip_address(entry)
        except ValueError:
            errors.append(f"'network.allowed_ips' contains an invalid IP/CIDR: {entry!r}")

    return errors


_VALIDATORS = {
    "self_only": _validate_self_only,
    "resource_attributes": _validate_resource_attributes,
    "context_attributes": _validate_context_attributes,
    "security_context": _validate_security_context,
    "time": _validate_time,
    "date_range": _validate_date_range,
    "network": _validate_network,
}
