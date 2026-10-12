import ipaddress
from collections.abc import Callable
from datetime import date
from datetime import time as dt_time
from zoneinfo import available_timezones


class ConditionValidationError(ValueError):
    """Raised by validate_conditions. Carries every problem found (not
    just the first) so a caller with several mistakes gets one useful
    error instead of fixing issues one at a time."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


# Mirrors default_condition_registry, kept as its own explicit set so this
# validator's key list is a deliberate contract, not just whatever
# handlers happen to be registered.
_SUPPORTED_KEYS: set[str] = {
    "self_only",
    "resource_attributes",
    "context_attributes",
    "time",
    "date_range",
    "network",
    "security_context",
}

# resource_attributes/context_attributes/security_context only check "is a
# non-empty dict" and never look inside the values, so without these limits
# a policy could carry a pathological key count, nesting depth, or string
# size (measured: a 150k-key dict took over a second and re-walks fully on
# every evaluation; deep nesting crashed the response serializer). Generous
# for any real condition (deepest built-in shape is 2 levels).
_MAX_CONDITION_DEPTH = 10
_MAX_CONDITION_NODES = 2000
_MAX_CONDITION_STRING_LENGTH = 2000


def validate_conditions(conditions: dict | None) -> None:
    """
    Validates a policy's whole `conditions` block before it's persisted.
    None/empty is valid (unconditional grant).

    Raises ConditionValidationError if `conditions` isn't a JSON object,
    has a key outside the supported vocabulary, or a value fails its
    condition type's shape/type/range checks; collects every problem, not
    just the first.

    Called before any database write, so bad data never reaches storage
    with a clear error explaining why. Complements
    ConditionEvaluationService's own fail-safe deny-on-unknown-key at
    evaluation time, which guards against conditions that got into the
    database some other way (direct write, migration).
    """
    if conditions is None:
        return
    if not isinstance(conditions, dict):
        raise ConditionValidationError(["'conditions' must be a JSON object"])

    size_errors = _validate_size_and_depth(conditions)
    if size_errors:
        # Fail fast on shape alone: skip the per-key validators below,
        # which would otherwise iterate the same oversized/deeply nested
        # structure a second time for no benefit.
        raise ConditionValidationError(size_errors)

    errors: list[str] = []
    for key, value in conditions.items():
        validator = _VALIDATORS.get(key)
        if validator is None:
            errors.append(f"Unknown condition key '{key}'")
            continue
        errors.extend(validator(value))

    if errors:
        raise ConditionValidationError(errors)


def sanitize_conditions_for_read(conditions: dict | None) -> dict | None:
    """
    Read-side counterpart to validate_conditions: called from PolicyRead
    so a policy whose `conditions` predates this validator, or was written
    some other way, can't crash the whole list/get response. Pydantic's
    serializer raises on any sufficiently deep dict, not just an actual
    cycle, so a pathological but valid stored value can 500 every caller
    of GET /authorization/policies. Replaces an oversized/too-deep value
    with a short marker instead of handing it to the serializer.
    """
    if conditions is None or not _validate_size_and_depth(conditions):
        return conditions
    return {"_error": "conditions omitted: exceeds size/depth limits, needs repair via direct DB access"}


def _validate_size_and_depth(conditions: dict) -> list[str]:
    """
    Cheap structural guard applied before per-key validation: caps total
    node count, nesting depth, and string length across the whole tree.

    Walked iteratively with an explicit stack, not recursion: a
    deliberately deep payload must not raise RecursionError while still
    being checked, which would turn a clean 422 into an unhandled 500.
    """
    errors: list[str] = []
    stack: list[tuple[object, int]] = [(conditions, 0)]
    node_count = 0
    while stack:
        node, depth = stack.pop()
        node_count += 1
        if node_count > _MAX_CONDITION_NODES:
            errors.append(f"'conditions' contains too many nested keys/items (max {_MAX_CONDITION_NODES})")
            break
        if depth > _MAX_CONDITION_DEPTH:
            errors.append(f"'conditions' is nested too deeply (max depth {_MAX_CONDITION_DEPTH})")
            break

        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and len(key) > _MAX_CONDITION_STRING_LENGTH:
                    errors.append(f"'conditions' contains a key longer than {_MAX_CONDITION_STRING_LENGTH} characters")
                    break
                stack.append((value, depth + 1))
        elif isinstance(node, list):
            stack.extend((item, depth + 1) for item in node)
        elif isinstance(node, str) and len(node) > _MAX_CONDITION_STRING_LENGTH:
            errors.append(f"'conditions' contains a string value longer than {_MAX_CONDITION_STRING_LENGTH} characters")
            break

    return errors


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
    # Only "start"/"end" are recognized (mirrors DateRangeCondition.evaluate);
    # aliases like "start_date"/"end_date" fail the check below like an
    # empty dict would.
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


_VALIDATORS: dict[str, Callable[[object], list[str]]] = {
    "self_only": _validate_self_only,
    "resource_attributes": _validate_resource_attributes,
    "context_attributes": _validate_context_attributes,
    "security_context": _validate_security_context,
    "time": _validate_time,
    "date_range": _validate_date_range,
    "network": _validate_network,
}


def register_condition_validator(key: str, validator: Callable[[object], list[str]]) -> None:
    """Register a downstream condition validator without editing this module.

    The matching handler is registered by ``register_condition_type`` in the
    condition registry.  Registration is intentionally additive: replacing a
    built-in or previously registered key would let an app silently change
    the meaning of existing policies.
    """
    if not isinstance(key, str) or not key or key.strip() != key:
        raise ValueError("condition key must be a non-empty string without surrounding whitespace")
    if key in _SUPPORTED_KEYS:
        raise ValueError(f"condition key is already registered: {key}")
    _SUPPORTED_KEYS.add(key)
    _VALIDATORS[key] = validator
