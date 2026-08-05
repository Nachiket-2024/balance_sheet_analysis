# Policy JSON Examples

A policy's fields (see `authorization/models/policy_model.py` / `authorization/schemas/policy_schema.py`):

| Field | Type | Notes |
|---|---|---|
| `name` | string | Unique, looked up by name everywhere; no `get_by_id`. |
| `description` | string, optional | Human-readable, for audit/inspection only, never evaluated. |
| `actions` | list[string] | Action identifiers this policy grants, e.g. `"users:read_own"`. |
| `resource_type` | string | The resource type this policy applies to, or `"*"` for resource-agnostic. |
| `conditions` | object, optional | See [Condition Schema Reference](condition-schema-reference.md). `null`/omitted = unconditional grant. |
| `is_active` | bool | Inactive policies are never evaluated as granting access. |

All examples below are the request body for `POST /authorization/policies` (requires `policies:create`, and the caller must already hold every action being granted; see [Architecture: Authorization Service](architecture.md#authorization-service)).

## Basic allow policy (unconditional)

Grants read access to a `documents` resource type, no restrictions:

```json
{
  "name": "document_reader",
  "description": "Read-only access to all documents",
  "actions": ["documents:view"],
  "resource_type": "documents"
}
```

---

## Policy with a time-based condition

Only grants access during business hours (Sydney time):

```json
{
  "name": "business_hours_reports",
  "description": "Report access, business hours only",
  "actions": ["reports:view"],
  "resource_type": "reports",
  "conditions": {
    "time": {
      "start": "09:00",
      "end": "17:00",
      "timezone": "Australia/Sydney"
    }
  }
}
```

---

## Policy with a network-based condition

Only grants access from the corporate network:

```json
{
  "name": "office_only_admin_panel",
  "description": "Admin panel access, corporate network only",
  "actions": ["admin_panel:view"],
  "resource_type": "admin_panel",
  "conditions": {
    "network": {
      "allowed_ips": ["10.0.0.0/8", "203.0.113.7"]
    }
  }
}
```

---

## Policy with a user-attribute condition (ownership)

Grants access to a resource only when the caller owns it: the resource's `email` field must match the caller's own email:

```json
{
  "name": "self_service",
  "description": "Baseline access every account gets: read and update one's own user profile.",
  "actions": ["users:read_own", "users:update_own"],
  "resource_type": "users",
  "conditions": {
    "self_only": true
  }
}
```

> This is the actual seeded `self_service` policy's shape shown for illustration. The real seeded row has no `conditions` at all, because the "own-ness" is already enforced structurally (the `/users/me` routes only ever fetch the caller's own record by their own email; see `api/user_routes/user_self_service_routes.py`). Use `self_only` when a route passes an arbitrary target resource and needs the *policy* to enforce ownership instead.

---

## Policy combining multiple condition types

Conditions are AND'ed across keys: every present key must pass:

```json
{
  "name": "contractor_temp_access",
  "description": "Temporary contractor access: business hours, office network, active contract window",
  "actions": ["projects:view"],
  "resource_type": "projects",
  "conditions": {
    "time": {"start": "09:00", "end": "18:00", "timezone": "UTC"},
    "network": {"allowed_ips": ["10.0.0.0/8"]},
    "date_range": {"start": "2026-01-01", "end": "2026-03-01"}
  }
}
```

---

## System superuser policy (seeded)

The most sensitive policy in the system: it assigns the system role and manages the authorization system itself. Resource type `"*"` because its actions span both `users` and `policies` resource types:

```json
{
  "name": "system_superuser",
  "description": "The most sensitive actions: assigning the system role and managing the authorization system itself.",
  "actions": [
    "users:assign_system_role",
    "policies:read",
    "policies:create",
    "policies:update",
    "policies:delete",
    "policies:assign",
    "policies:revoke",
    "security_audit:read",
    "users:purge",
    "users:reactivate"
  ],
  "resource_type": "*",
  "is_active": true
}
```

This policy is seeded by `backend/alembic/versions/b7d3a1c9e4f2_add_pbac_policies.py` and updated in place by later data migrations as capabilities changed. The current migrated shape includes the fine-grained `policies:*` actions, `security_audit:read`, `users:purge`, and `users:reactivate`. It is protected: it can never be deleted or renamed via the management API (see [Writing and Testing Policies](writing-testing-policies.md#protected-baseline-policies)), and its last assignment can never be revoked (would leave nobody able to manage the authorization system at all).

---

## User administration policy (seeded)

```json
{
  "name": "user_administration",
  "description": "Manage other users' accounts: list, update, delete, assign non-system roles.",
  "actions": ["users:list_all", "users:update_any", "users:delete_any", "users:assign_role"],
  "resource_type": "users",
  "is_active": true
}
```

---

## Self-service policy (seeded, actual shape)

The baseline every new account receives automatically at signup/OAuth2 (see [Adding New Permissions](adding-permissions.md#roles-vs-policies)):

```json
{
  "name": "self_service",
  "description": "Baseline access every account gets: read and update one's own user profile.",
  "actions": ["users:read_own", "users:update_own"],
  "resource_type": "users",
  "is_active": true
}
```
