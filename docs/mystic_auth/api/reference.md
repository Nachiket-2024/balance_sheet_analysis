# API Reference

Full route inventory, grouped by `APIRouter` module under `backend/mystic_auth/api/`. All routers are mounted in `backend/app/main.py`. Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are available whenever `ENVIRONMENT != "production"`; see [Backend Architecture](../architecture/backend.md#request-pipeline).

Every request/response body is a Pydantic schema (`*_schema.py` beside each feature); FastAPI validates the body and returns `422` with a field-by-field error list on a bad payload, so no route does its own manual validation.

## Conventions

- **Auth requirement** `session` means "a valid `access_token` cookie, no specific permission" (`Depends(get_current_user)`); a `permission:action` value means `Depends(require_authorization(action, resource_type))`, see [PBAC Architecture](../authorization/architecture.md). `public` means no cookie required at all.
- All cookies are httpOnly; the API is never called with a bearer token/header. See [Authentication Overview](../authentication/overview.md#tokens-and-cookies).
- Rate-limited routes (marked below) are gated by `rate_limiter_service.rate_limited(...)`. See [Security Hardening](../security/hardening.md#rate-limiting).

## Authentication: `/auth` (`api/auth_routes/auth_routes.py`)

| Method | Path | Auth | Rate limited | Notes |
|---|---|---|---|---|
| POST | `/auth/signup` | public | per-email | See [Authentication Overview](../authentication/overview.md#signup) |
| POST | `/auth/login` | public | per-IP + per-account, plus lockout | See [Login](../authentication/overview.md#login) |
| GET | `/auth/oauth2/login/google` | public | yes | Redirects to Google consent screen, see [OAuth2 / PKCE](../authentication/oauth2-pkce.md) |
| GET | `/auth/oauth2/callback/google` | public | yes | Google redirects here with `code`/`state` |
| GET | `/auth/me` | session | yes | Re-verifies JWT + re-queries user row every call |
| POST | `/auth/logout` | session (needs `refresh_token` cookie) | yes | Revokes one refresh token `jti` |
| POST | `/auth/logout/all` | session | yes | Revokes every refresh token `jti` for the account |
| POST | `/auth/password-reset/request` | public | per-email | Always returns the same generic response |
| POST | `/auth/password-reset/confirm` | public | yes | Revokes all refresh tokens on success |
| POST | `/auth/verify-account` | public | yes | Single-use Redis-backed token |
| POST | `/auth/verify-account/request` | public | per-email | Always returns the same generic response |

## Refresh token: `/auth/refresh` (`api/auth_routes/refresh_token_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/refresh/` | session (needs `refresh_token` cookie, scoped to `/auth` path) | Rotates the refresh token; reused-token detection revokes every token for the user, see [Refresh Token Rotation](../authentication/overview.md#refresh-token-rotation) |

## Users: `/users` (`api/user_routes/user_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/users/me` | `users:read_own` | Caller's own profile |
| PUT | `/users/me` | `users:update_own` | Accepts an optional `password` field, hashed and renamed before reaching the CRUD layer, see [Database Design](../database/design.md#users). If `password` is set and the account already has one, a matching `current_password` is also required, see [Security Decisions](../security/decisions.md#self-service-password-change-requires-the-current-password) |
| GET | `/users/` | `users:list_all` | All users |
| PUT | `/users/{user_email}` | `users:update_any` | System account is excluded via a target-account guard |
| DELETE | `/users/{user_email}` | `users:delete_any` | Soft delete, see [Account Lifecycle](../database/design.md#account-lifecycle) |
| DELETE | `/users/{user_email}/purge` | `users:purge` | Hard delete, irreversible |
| PATCH | `/users/{user_email}/reactivate` | `users:reactivate` | Reverses a soft delete |
| PATCH | `/users/{user_email}/role` | `users:assign_role` or `users:assign_system_role` (depends on target role) | The single, bidirectional role-modification endpoint; there is no separate "promote" path. Assigning `system` role requires the more sensitive action |

## Authorization / PBAC: `/authorization` (`api/pbac_routes/*.py`)

Split across `policy_crud_routes.py`, `policy_history_routes.py`, `policy_assignment_routes.py`, `authorization_check_routes.py`, `pbac_audit_log_routes.py`. See [PBAC Architecture: full route list](../authorization/architecture.md#full-route-list) for the complete, permission-annotated table (policies CRUD, history/rollback, assignment, the inspection/batch-check endpoints, and the PBAC audit log).

## Security audit log: `/audit` (`api/audit_log_routes/audit_log_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/audit/security-log` | permission-gated (see route) | Login/logout/signup/OAuth2/lockout/account-lifecycle events, distinct from the PBAC audit log, see [Database Design: why two audit tables](../database/design.md#why-two-audit-tables-not-one) |
| GET | `/audit/security-log/me` | session | Caller's own security events only |

## Health: no prefix (`api/health_routes/health_routes.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | public | Liveness: process is up |
| GET | `/health/ready` | public | Readiness: confirms Postgres and Redis connectivity; used by Docker healthchecks, see [Docker Overview](../docker/overview.md) |

## Root

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/` | public | `{"message": "Welcome to <APP_NAME>!"}` (product name from the `APP_NAME` env var); liveness sanity check, not part of any real integration |

## Error responses

Every route shares one global exception handler (`main.py`'s `@app.exception_handler(Exception)`): any unhandled exception is logged with a stack trace and returned as a generic `500 {"detail": "Internal Server Error"}`, so no internal exception detail (message, type, traceback) ever reaches the client. Expected failures use FastAPI's normal `HTTPException` mechanism (`400`/`401`/`403`/`404`/`409`/`422`) with a specific `detail` message per case.
