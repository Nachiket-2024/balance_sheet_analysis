# PBAC Architecture: Full Route List

---

## Full route list

| Method | Path | Permission required |
|---|---|---|
| POST | `/authorization/policies` | `policies:create` |
| GET | `/authorization/policies` | `policies:read` |
| GET | `/authorization/policies/{name}` | `policies:read` |
| PUT | `/authorization/policies/{name}` | `policies:update` |
| DELETE | `/authorization/policies/{name}` | `policies:delete` |
| GET | `/authorization/policies/{name}/history` | `policies:read` |
| GET | `/authorization/policies/{name}/history/compare` | `policies:read` |
| POST | `/authorization/policies/{name}/history/{id}/rollback` | `policies:update` |
| POST | `/authorization/users/{email}/policies` | `policies:assign` |
| DELETE | `/authorization/users/{email}/policies/{name}` | `policies:revoke` |
| POST | `/authorization/users/{email}/policies/{name}/revoke-action` | `policies:revoke` and `permissions:grant` (see [Policy Action Revocation](component-responsibilities.md#policy-action-revocation)) |
| GET | `/authorization/users/{email}/policies` | `policies:read` |
| GET | `/authorization/users/me/policies` | any authenticated user (self-service) |
| POST | `/authorization/users/{email}/authorization-check` | `policies:read` |
| POST | `/authorization/batch-check` | `users:read_own` (checks the caller's own authorization) |
| GET | `/authorization/audit-log` | `policies:read` |
| GET | `/authorization/audit-log/me` | any authenticated user |
| GET | `/authorization/audit-log/users/{email}` | `policies:read` |
| POST | `/authorization/users/{email}/permissions` | `permissions:grant` |
| DELETE | `/authorization/users/{email}/permissions/{action}` | `permissions:revoke` |
| GET | `/authorization/users/{email}/permissions` | `permissions:read` |
| GET | `/authorization/users/me/permissions` | any authenticated user (self-service) |
| GET | `/authorization/permissions/catalog` | any of `permissions:read`, `policies:create`, `policies:update`, `permissions:grant` (the create/edit policy form and the direct-grant form need this list too, without needing `permissions:read` itself) |
| GET | `/authorization/permissions/catalog/usage` | `permissions:read` (narrower than the catalog above: this discloses who actually holds each action, which a policy/grant form doesn't need) |
| POST | `/authorization/bulk/policies/assign` | `policies:assign` |
| POST | `/authorization/bulk/policies/remove` | `policies:revoke` |
| POST | `/authorization/bulk/permissions/assign` | `permissions:grant` |
| POST | `/authorization/bulk/permissions/remove` | `permissions:revoke` |
| POST | `/authorization/bulk/users/role` | `users:assign_role` |

Direct permission grants (`UserPermission`, bypassing `Policy` entirely) are covered in [Adding New Permissions: Direct grants vs. policies](../adding-permissions.md#direct-grants-vs-policies), including how `AuthorizationService._get_effective_policies` normalizes them into the same evaluation path as a real policy. The bulk endpoints above apply one operation (policy assign/remove, permission grant/remove, or role set) to many target users in a single request; each accepts a list of targets and returns one per-item success/error result rather than failing the whole batch on one bad target, all committed in a single transaction per batch.

`/users/{email}/role` and `/authorization/bulk/users/role` additionally reject a target equal to the caller's own email, regardless of which role is requested; see [`users.role` is display-only, and is guarded as if it weren't](README.md#usersrole-is-display-only-and-is-guarded-as-if-it-werent).

---

See [PBAC Architecture](README.md) for the request flow.

---
