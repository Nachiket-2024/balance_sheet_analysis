# Condition Schema Reference

A policy's `conditions` field is a JSON object where each key is a condition type. All present keys are AND'ed: every one must pass for the policy to grant access on a given check. `conditions: null` (or omitted) means an unconditional grant.

Every condition type has **exactly one** canonical field-name shape, enforced identically by two independent layers:

1. **`authorization/conditions/condition_validator.py`**: rejects an invalid `conditions` block at `POST`/`PUT /authorization/policies` time, before any database write.
2. **The matching handler in `authorization/conditions/*.py`**: fails safe (denies) at evaluation time if it somehow receives something the validator didn't catch (e.g. a row written directly to the database).

This is deliberate defense in depth, not redundancy: the validator stops bad data from being stored at all; the handler's own fail-safe protects real requests even if bad data got in some other way.

An **unrecognized condition key** is rejected by the validator and, if it ever reached evaluation anyway, denied by `ConditionEvaluationService`; it is never silently ignored.

---

## `self_only`

Ownership check: the resource's `email` field must match the acting user's own email.

```json
{"self_only": true}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| *(value)* | boolean | yes | `false` imposes no restriction (same as omitting the key). |

**Validation rule:** must be a boolean.
**Evaluation rule:** denies if no `resource` was supplied at all, since an ownership check with nothing to check ownership against cannot be assumed true.

## `resource_attributes`

Every listed field must equal its expected value on the resource being acted on.

```json
{"resource_attributes": {"status": "draft"}}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| *(value)* | non-empty object | yes | `{field: expected_value, ...}`. |

**Validation rule:** must be a non-empty object.
**Evaluation rule:** denies if no `resource` was supplied.

> **Modeling a hierarchy (org chart, company group, folder tree) with this flat-equality condition**: see [Common Patterns: scoping access to a hierarchy](common-patterns.md#scoping-access-to-a-hierarchy-org-chart-company-group-folder-tree): the technique is a denormalized ancestor-id column on your own resource table, not a new condition type.

## `context_attributes`

Every listed key must match its expected value in the caller-supplied `context` dict (generic, application-defined signals, e.g. `{"mfa_verified": true}`).

```json
{"context_attributes": {"department": "finance"}}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| *(value)* | non-empty object | yes | `{key: expected_value, ...}`. |

**Validation rule:** must be a non-empty object.
**Evaluation rule:** denies if no `context` was supplied.

## `time`

The current wall-clock time (in the given timezone) must fall within `[start, end]`.

```json
{
  "time": {
    "start": "09:00",
    "end": "17:00",
    "timezone": "Australia/Sydney"
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `start` | string, `"HH:MM"` | yes | ISO time format. |
| `end` | string, `"HH:MM"` | yes | ISO time format. |
| `timezone` | string, IANA name | no | Defaults to UTC. Must be a name from Python's `zoneinfo.available_timezones()`. |

**Validation rules:** `start`/`end` required and must parse as ISO times; `timezone`, if given, must be a real IANA timezone name.
**Evaluation rules:** supports **overnight ranges** where `start > end` (e.g. `"22:00"`-`"06:00"` wraps past midnight). Denies if `start`/`end` are missing or malformed, or the timezone is invalid; it is never silently treated as unconditional.
**Real-time override for testing/simulation:** if `context["current_time"]` is an ISO 8601 datetime string, it's used instead of the real clock (see `authorization/conditions/clock.py`): this is what lets the `/authorization-check` inspection endpoint answer "what if it were this time?", and what makes this condition deterministically unit-testable.

## `date_range`

The current date (UTC) must fall within `[start, end]`. Used for temporary/contractor access windows and expiring permissions.

```json
{
  "date_range": {
    "start": "2026-01-01",
    "end": "2026-03-01"
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `start` | string, `"YYYY-MM-DD"` | at least one of `start`/`end` | Omit for "access until `end`". |
| `end` | string, `"YYYY-MM-DD"` | at least one of `start`/`end` | Omit for "access from `start` on". |

> **Canonical names are `start`/`end`**, matching `time`'s own naming, for consistency. `start_date`/`end_date` (or any other alias) are **not** recognized; a policy using them is rejected by the validator (fails the "requires at least one of `start` or `end`" check), and even if such a row somehow reached evaluation, the handler denies rather than treating it as unconstrained.

**Validation rules:** must be an object with at least one of `start`/`end` present; each present bound must parse as an ISO date.
**Evaluation rules:** denies if *neither* bound is present at all (this can only happen via direct DB manipulation, since the validator blocks it at write time): a `date_range` condition with no recognizable bound must never be treated as unconstrained.

## `network`

The caller's IP (from the real request connection, see [Architecture: Context Builder](architecture.md#authorization-context-builder)) must match one of the listed single IPs or CIDR ranges.

```json
{
  "network": {
    "allowed_ips": ["10.0.0.0/8", "203.0.113.7"]
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `allowed_ips` | non-empty list of strings | yes | Each entry either a single IP or a CIDR range (contains `/`). |

**Validation rules:** `allowed_ips` must be a non-empty list; every entry must parse as a valid IP address or CIDR network.
**Evaluation rules:** denies if `allowed_ips` is empty, the context carries no `ip_address` at all, or the caller's IP fails to parse.

## `security_context`

Every listed key must match its expected value in `context["security_context"]`, the reserved sub-key every real request context carries (see [Architecture: Context Builder](architecture.md#authorization-context-builder)).

```json
{
  "security_context": {
    "device_trusted": true
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| *(value)* | non-empty object | yes | `{key: expected_value, ...}`. |

**Validation rule:** must be a non-empty object.
**Evaluation rule:** denies if `context["security_context"]` is missing entirely, or any listed key is absent from it.

> This app does not implement MFA/device-trust infrastructure itself: `security_context` only checks whatever fields a future trust-signal layer populates. Today, `build_authorization_context` always sets it to `{}`, so any `security_context` condition currently always denies (there's nothing populating it yet). This is intentional, not a bug, until that layer is built.

---

## Combining condition types

All present keys are AND'ed:

```json
{
  "conditions": {
    "time": {"start": "09:00", "end": "18:00"},
    "network": {"allowed_ips": ["10.0.0.0/8"]}
  }
}
```

This grants access only during business hours **and** from the corporate network; both must pass.
