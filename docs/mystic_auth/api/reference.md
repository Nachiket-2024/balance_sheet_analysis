# API Reference
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

Full route inventory, grouped by `APIRouter` module under `backend/mystic_auth/api/`. All routers are mounted in `backend/app/main.py`. Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are available whenever `ENVIRONMENT != "production"`; see [Backend Architecture](../architecture/backend.md#request-pipeline).

Every request/response body is a Pydantic schema (`*_schema.py` beside each feature); FastAPI validates the body and returns `422` with a field-by-field error list on a bad payload, so no route does its own manual validation.

---

## Conventions

- **Auth requirement** `session` means "a valid `access_token` cookie, no specific permission" (`Depends(get_current_user)`); a `permission:action` value means `Depends(require_authorization(action, resource_type))`, see [PBAC Architecture](../authorization/architecture/README.md). `public` means no cookie required at all.
- All cookies are httpOnly; the API is never called with a bearer token/header. See [Authentication Overview](../authentication/overview.md#tokens-and-cookies).
- Rate-limited routes (marked below) are gated by `rate_limiter_service.rate_limited(...)`. See [Security Hardening: Abuse Prevention](../security/hardening-abuse-prevention.md#rate-limiting).

---

### List endpoint conventions

Every endpoint that returns a list of rows (`GET /users/`, and the audit log endpoints below) shares the same shape, rather than each inventing its own:

- `limit`/`offset` page through the result set; the response body stays a plain `list[...]` (`response_model` is never a wrapper object), so the total row count instead rides an **`X-Total-Count`** response header. This lets the frontend render numbered pages (see [Frontend Architecture: List pages](../architecture/frontend.md#list-pages-pagination-sorting-filtering)) without a second round trip just to learn how many there are.
- `sort_by`/`sort_dir` (`asc`/`desc`) sort the whole result set, not just the returned page. `sort_by` is checked against a small, explicit allowlist of real columns per endpoint, such as `user_base_crud.py`'s `_SORTABLE_COLUMN_NAMES` and the two audit log repositories' `_SORTABLE_COLUMNS`. Caller-supplied strings never reach a query as raw column names. An unrecognized or omitted value falls back to a sensible default order.
- Free-text fields (`search` on user name/email or audit log `user_email`, `ip_address`) are case-insensitive substring matches; fixed-vocabulary fields (`role`, `is_verified`, `status`, `action`, `resource_type`, `allowed`, `event_type`, `success`) are exact matches. `X-Total-Count` is always computed from the exact same filters as the row query, so a filtered page's reported total is never out of sync with what's actually being paged through.

---

## Authentication: `/auth` (`api/auth_routes/auth_routes.py`)

| Method | Path | Auth | Rate limited | Notes |
|---|---|---|---|---|
| POST | `/auth/signup` | public | per-email | See [Signup and Email Verification](../authentication/signup-and-verification.md) |
| POST | `/auth/login` | public | per-IP + per-account, plus lockout | See [Login](../authentication/login.md) |
| GET | `/auth/oauth2/login/google` | public | yes | Redirects to Google consent screen, see [OAuth2 / PKCE](../authentication/oauth2-pkce.md) |
| GET | `/auth/oauth2/callback/google` | public | yes | Google redirects here with `code`/`state` |
| GET | `/auth/me` | session | yes | Re-verifies JWT + re-queries user row every call |
| POST | `/auth/logout` | session (needs `refresh_token` cookie) | yes | Bumps that one session's `chain_ver`, ending just this device. Always `200`; response carries `session_revoked: false` if the bump couldn't be confirmed (Postgres unavailable) |
| POST | `/auth/logout/all` | session | yes | Bumps `account_ver`, ending every session on the account. Returns `503` (`SESSION_REVOCATION_UNAVAILABLE`) instead of a false success if the bump couldn't be confirmed, see [Session Management: bump failure handling](../authentication/session-management/token-lifecycle.md#bump-failure-handling) |
| GET | `/auth/sessions` | session | yes | Lists the caller's active sessions ("Manage Sessions" dashboard card), see [Database Design: user_sessions](../database/design.md) |
| DELETE | `/auth/sessions/{session_id}` | session (ownership-checked) | yes | Ends one session by id; rejects the caller's own current session with `400` (use Logout instead). Returns `503` (`SESSION_REVOCATION_UNAVAILABLE`) instead of a false success if the underlying chain-version bump couldn't be confirmed |
| GET | `/auth/session-events` | session | no (long-lived connection) | Server-Sent Events stream; pushes a "something changed" nudge on session revoke/create and on a policy grant/revoke/edit/delete/rollback affecting this account, see [Session Management: Real-time push](../authentication/session-management/real-time-push.md#real-time-push) and [PBAC Architecture: Real-time push](../authorization/architecture/real-time-push.md#real-time-push) |
| POST | `/auth/password-reset/request` | public | per-email | Always returns the same generic response |
| POST | `/auth/password-reset/confirm` | public | yes | The new password always succeeds independent of Valkey; response carries `sessions_revoked: false` if the other-session revoke couldn't be confirmed, see [Session Management: bump failure handling](../authentication/session-management/token-lifecycle.md#bump-failure-handling) |
| POST | `/auth/verify-account` | public | yes | Single-use Valkey-backed token |
| POST | `/auth/verify-account/request` | public | per-email | Always returns the same generic response |

---

## Refresh token: `/auth/refresh` (`api/auth_routes/refresh_token_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/refresh` | session (needs `refresh_token` cookie, scoped to `/auth` path) | Canonical no-slash form; rotates the refresh token without an HTTP redirect. Reused-token detection revokes only that rotation chain, see [Rotation chains and reuse detection](../authentication/session-management/token-lifecycle.md#rotation-chains-and-reuse-detection) |
| POST | `/auth/refresh/` | session (needs `refresh_token` cookie, scoped to `/auth` path) | Rotates the refresh token; reused-token detection revokes only that rotation chain, see [Rotation chains and reuse detection](../authentication/session-management/token-lifecycle.md#rotation-chains-and-reuse-detection) |

---

## Users: `/users` (`api/user_routes/user_self_service_routes.py`, `user_management_query_routes.py`, `user_management_update_routes.py`, `user_lifecycle_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/users/me` | `users:read_own` | Caller's own account details, backing the Account Settings page |
| PUT | `/users/me` | `users:update_own` | Accepts an optional `password` field, hashed and renamed before reaching the CRUD layer, see [Database Design](../database/design.md#users). If `password` is set and the account already has one, a matching `current_password` is also required, see [Security Decisions](../security/decisions-auth.md#self-service-password-change-requires-the-current-password). A password change always succeeds (independent of Valkey), but the response's `sessions_revoked` field is `false` if the other-session revoke couldn't be confirmed, see [Session Management: bump failure handling](../authentication/session-management/token-lifecycle.md#bump-failure-handling) |
| DELETE | `/users/me` | `users:update_own` | Self-service delete. Password accounts: soft-deletes synchronously (requires `current_password`). OAuth-only accounts: sends a confirmation email instead, `{"confirmation_required": true}`, nothing deleted yet. See [Account Deletion and Purge](../authentication/account-deletion/README.md) |
| POST | `/users/me/confirm-delete` | public | Rate-limited. Redeems the OAuth-only-account deletion confirmation link (`token`), single-use; own `account_delete_confirm_lock:` lockout namespace |
| GET | `/users/stats` | `users:list_all` | Aggregate whole-table counts for the Users page summary card: total, verified, unverified, inactive. Uses the same permission as `/users/` because it is another view of the same user-management data |
| GET | `/users/` | `users:list_all` | All users; supports `search`/`role`/`is_verified`/`status`/`policy`/`permission`/`permission_source`/`last_login`/`last_login_from`/`last_login_to`/`sort_by`/`sort_dir`, see [List endpoint conventions](#list-endpoint-conventions). `policy` matches users holding that policy by name; `permission` matches an action held either via a policy or a direct grant, narrowed to just one source with `permission_source` (`policy` or `direct`); `last_login` is a relative bucket (`today`/`7d`/`30d`/`90d`/`never`), ignored if `last_login_from`/`last_login_to` (an explicit range) are set instead |
| GET | `/users/export` | `users:list_all` | CSV export of every user matching the same filters as `GET /users/` above (no `limit`/`offset`: always the whole filtered set). Rejected with `400 EXPORT_TOO_LARGE` if the filtered set exceeds `USER_EXPORT_MAX_ROWS` (`env/mystic_auth/.env.dev.example`, default `50000`); narrow the filters instead |
| PUT | `/users/{user_email}` | `users:update_any` | System account is excluded via a target-account guard. Same `sessions_revoked` contract as `PUT /users/me` on a password change, see [Session Management: bump failure handling](../authentication/session-management/token-lifecycle.md#bump-failure-handling) |
| DELETE | `/users/{user_email}` | `users:deactivate_any` | Soft delete, see [Account Lifecycle](../database/design.md#account-lifecycle). The delete always succeeds; an unconfirmed session revoke is recorded in the audit log rather than erroring the request, see [Session Management: bump failure handling](../authentication/session-management/token-lifecycle.md#bump-failure-handling) |
| DELETE | `/users/{user_email}/purge` | `users:delete_any` | Hard delete, irreversible. Fails closed: returns `503` (`SESSION_REVOCATION_UNAVAILABLE`) and deletes nothing if the pre-delete session revoke can't be confirmed, see [Session Management: bump failure handling](../authentication/session-management/token-lifecycle.md#bump-failure-handling) |
| PATCH | `/users/{user_email}/reactivate` | `users:reactivate` | Reverses a soft delete |
| PATCH | `/users/{user_email}/role` | `users:assign_role` or `users:assign_system_role` (depends on target role) | The single, bidirectional role-modification endpoint; there is no separate "promote" path. Assigning `system` role requires the more sensitive action |

---

## Authorization / PBAC: `/authorization` (`api/pbac_routes/*.py`)

Split across `policies/policy_crud_routes.py`, `policies/policy_history_routes.py`, `policies/policy_assignment_routes.py`, `permissions/permission_assignment_routes.py`, `permissions/permission_catalog_routes.py`, `bulk/bulk_policy_routes.py`, `bulk/bulk_permission_routes.py`, `bulk/bulk_role_routes.py`, `authorization_check_routes.py`, `pbac_audit_log_routes.py`. See [PBAC Architecture: full route list](../authorization/architecture/full-route-list.md#full-route-list) for the complete, permission-annotated table (policies CRUD, history/rollback, assignment, direct permission grants, the permission catalog, bulk operations, the inspection/batch-check endpoints, and the PBAC audit log). `revoke-action` is a variant of assignment removal that carves a single action out of a policy assignment instead of dropping it whole - see [Policy Action Revocation](../authorization/architecture/component-responsibilities.md#policy-action-revocation). The three PBAC audit log endpoints (`/authorization/audit-log`, `/audit-log/me`, `/audit-log/users/{email}`) support `search`/`action`/`resource_type`/`allowed`/`sort_by`/`sort_dir` the same way the security audit log does, see [List endpoint conventions](#list-endpoint-conventions).

---

## Security audit log: `/audit` (`api/audit_log_routes/audit_log_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/audit/security-log` | permission-gated (see route) | Login/logout/signup/OAuth2/lockout/account-lifecycle/session-revoke events, distinct from the PBAC audit log, see [Database Design: why two audit tables](../database/design.md#why-two-audit-tables-not-one). Supports `search`/`event_type`/`ip_address`/`success`/`from`/`to`/`sort_by`/`sort_dir`, see [List endpoint conventions](#list-endpoint-conventions). `from`/`to` filter on `created_at`, both inclusive |
| GET | `/audit/security-log/users/{user_email}` | `security_audit:read` | A specific user's security events; same filters as the list above minus `search` (already scoped to one user). Backs the User Access dialog's "Recent access changes" |
| GET | `/audit/security-log/me` | session | Caller's own security events only; same filters as the broader list above, minus `search` (already scoped to one user) |
| GET | `/audit/security-log/login-trend` | permission-gated (see route) | Daily login success/failure counts across every user for the last `days` (default 14, max 90), optionally narrowed by `search` (user email substring) and `from`/`to`; backs the Audit Log page's trend chart |
| GET | `/audit/security-log/me/login-trend` | session | Same trend, scoped to the caller's own login events, no `security_audit:read` required; supports `from`/`to` |

---

## Rate limits: `/rate-limits` (`api/rate_limit_routes/rate_limit_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/rate-limits/` | `rate_limits:read` | Lists live Valkey-backed rate-limit counters (Rate Limit Dashboard). Numbered pagination via `page`/`page_size`: the server walks the matching keyspace in bounded `SCAN` batches (never `KEYS`) up to a capped total (`RateLimitDashboardService.MAX_SCANNED_KEYS`) to compute `total` and slice out one page; `truncated: true` means that cap was hit, so `total` is a floor, not exact. `scope` (`ip`/`account`/`email`), `endpoint`, and `identifier` (substring on the IP/account) filter server-side; `kind` narrows to `at_limit` (counters currently at their cap) or `login_lockouts`; `sort_by` (`endpoint`/`scope`/`identifier`/`count`/`resets_at`) and `sort_dir` sort the matched set before paging. See [Security Hardening: Abuse Prevention](../security/hardening-abuse-prevention.md#rate-limiting) |
| GET | `/rate-limits/summary` | `rate_limits:read` | Bounded summary counts for the dashboard header tiles (`total`, `at_limit`, `login_lockouts`, per-endpoint and per-scope breakdowns), computed from the same capped keyspace scan as the list above |
| DELETE | `/rate-limits/{key}` | `rate_limits:reset` | Manually clears one counter, e.g. to unblock a legitimate caller who tripped a limit. Idempotent: always returns `204`, even if the key was already absent/expired. Its own action, separate from `rate_limits:read`, so a policy scoped to "can view the dashboard" doesn't also imply "can clear anyone's counters" - the same read/write split every other resource in `Permission` gets |

---

## Health: no prefix (`api/health_routes/health_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | public | Liveness: process is up |
| GET | `/health/ready` | public | Readiness: confirms Postgres and Valkey connectivity; used by Docker healthchecks, see [Docker Overview](../docker/overview.md) |

---

## Root

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/` | public | `{"message": "Welcome to <APP_NAME>!"}` (product name from the `APP_NAME` env var); liveness sanity check, not part of any real integration |

---

## Error responses

Every route shares one global exception handler (`main.py`'s `@app.exception_handler(Exception)`): any unhandled exception is logged with a stack trace and returned as a generic `500 {"detail": "Internal Server Error"}`, so no internal exception detail (message, type, traceback) ever reaches the client. Expected failures use FastAPI's normal `HTTPException` mechanism (`400`/`401`/`403`/`404`/`409`/`422`) with a specific `detail` message per case, or `core/errors.py`'s `AppError`, caught by a second, more specific `@app.exception_handler(AppError)` and returned as `{"detail", "code", "params"}`. `code` is a stable, machine-readable identifier (e.g. `"INVALID_CREDENTIALS"`) the frontend translates client-side (`api/apiError.ts`, see [Translations Overview](../translations/overview/ui-and-errors.md#5-backend-error-codes-frontendsrcmystic_authapiapierrorts)); routes not yet migrated to `AppError` fall back to a plain `HTTPException` `detail` string with no `code`. See [Security Hardening: HTTP Layer](../security/hardening-http.md#error-handling).

---
