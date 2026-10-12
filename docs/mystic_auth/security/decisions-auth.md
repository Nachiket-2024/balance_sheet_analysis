# Security Decisions: Auth & Session
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Authentication Glossary](../glossary/authentication.md).*

See [Security Decisions](decisions.md) for the full index, including infrastructure and product
decisions. This page covers the *why* behind authentication, session, and rate-limiting choices.

---

## Role is never used to decide access

PBAC (policy-based access control), not role-based access control. `users.role` is nullable, display/grouping metadata only: every real authorization decision goes through an assigned, active `Policy` (see [../authorization/architecture/README.md](../authorization/architecture/README.md)). Two accounts with the identical role can have completely different effective permissions, and a roleless account (`role=NULL`) can still be fully authorized via policies alone.

**Why not role-based access control**:

1. A static role-permission mapping means every new access pattern either overloads an existing role's meaning or requires a new role and a code deploy.
2. Policies are data, not code: a new access pattern is a new policy row, assignable and revocable per account without touching role definitions.
3. The tradeoff is real: PBAC has more moving parts than a role comparison. The `Permission` enum (`backend/mystic_auth/authorization/permissions.py`) still gives the action vocabulary the same fixed-set discipline a role enum would.

**Where this is enforced structurally, not just by convention**:

1. Every permission-protected route in `user_management_query_routes.py`, `user_management_update_routes.py`, and `user_lifecycle_routes.py` depends on `require_authorization(action, resource_type)`, never a role comparison.
2. The handful of `role ==` checks that do exist (e.g. "the system account cannot be modified via these generic endpoints") are resource-protection invariants: they protect one specific reserved account from *every* caller regardless of what that caller is otherwise authorized to do, not authorization decisions. See the `UserRole` import comment at the top of each file for the exact reasoning, repeated at each guard site.
3. The delete and purge routes additionally reject the caller acting on their own account, a self-lockout guard rather than an authorization decision.

---

## Why current-user lookups re-query the database every time

1. `current_user_handler.get_current_user` (called on every authenticated request) decodes the JWT *and* re-fetches the user row from Postgres, rather than trusting the token's claims alone.
2. This is the mechanism that makes account deactivation/soft-delete take effect on the very next request, instead of only once the access token's own (up-to-one-hour) `exp` is reached.
3. The cost is one extra DB round-trip per request. The alternative (trust the token until it expires) would mean a just-deleted or just-deactivated account could keep acting on the system for up to the full access-token lifetime.

---

## Email addresses are normalized, case-insensitively, everywhere

`User@Example.com` and `user@example.com` are the same account. Normalization (`emails/email_normalization.py::normalize_email`, strip + lowercase) happens at these layers, not scattered across every call site:

1. `UserEmailCRUD.get_by_email`/`update_by_email` normalize on every lookup, and `UserBaseCRUD.create` normalizes before every insert. Together these cover every path (signup, login, OAuth2, permission-protected routes) regardless of what casing the caller passes.
2. `signup_schema.py`/`login_schema.py`/`password_reset_request_schema.py`/`UserBase` also normalize at the input boundary, so the canonical lowercase form flows through logs/tokens/audit from the earliest point, not just at the DB.
3. `oauth2_service.py` normalizes explicitly right after reading `user_info.get("email")`, since that path is a raw dict from Google's response and never touches a Pydantic schema.
4. The permission-protected routes in `user_management_update_routes.py` and `user_lifecycle_routes.py` that take `user_email` as a path parameter normalize it before using it for lookups, session revocation, and audit logging, so a differently-cased path param still revokes the right sessions.

---

## Timing-attack mitigations

Applied consistently across every enumeration-sensitive endpoint:

- **Login** (`login_service.py`): the Argon2 password comparison always runs, against the real hash, or a fixed `DUMMY_HASH` if the account doesn't exist or has no password, *before* any existence/verification/active check. "Wrong password," "no such account," and "OAuth2-only account with no password" are all indistinguishable by response time.
- **Signup** (`signup_service.py`): the password is hashed unconditionally before the duplicate-email check, so a registered vs. unregistered email can't be distinguished by how fast the response comes back (only by the identical generic response body).
- **Password reset request**: always returns the same generic "if this email is registered..." message.

---

## Token replay and reuse detection

1. Refresh tokens are single-use. An atomic per-`jti` claim (`claim_jti_for_rotation`) marks one redeemed immediately after a successful rotation.
2. If a token whose `jti` is already claimed is presented again, a same-IP retry inside the brief configured grace period is rejected without revoking the first request's chain or minting another child. Older or cross-IP reuse bumps that token's own `chain_ver` (`revoke_chain_for_user`), killing that chain and logging the event at `critical` severity.
3. **This is deliberately scoped to the compromised chain, not every session on the account.** An earlier version bumped every session unconditionally, which meant a stale token replayed on any device could also kill an unrelated, never-compromised session created afterward. See [Session Management](../authentication/session-management/token-lifecycle.md#rotation-chains-and-reuse-detection) and [Authentication Overview](../authentication/overview.md#refresh-token-rotation).
4. A token minted before chain tracking existed carries no `chain` claim, so there's no lineage to scope to; reuse of one of those still falls back to the old, maximally-safe response (bumps `account_ver`, every session on the account).
5. **Version validity is checked *before* the reuse check, not just after.** A refresh token whose embedded `account_ver`/`chain_ver` has already fallen behind Postgres' durable version record is rejected as stale before `claim_jti_for_rotation` runs. Without that order, a session that was intentionally ended could still rotate into a new valid session on its next refresh, since the single-use claim only catches a token redeemed twice.
6. **Rotation is atomic, closing a concurrent-request race.** Two requests presenting the identical still-valid refresh token at the same time must not both be able to rotate it. `JWTService.claim_jti_for_rotation` uses a unique Postgres primary key on `consumed_refresh_tokens.jti` and `INSERT ... ON CONFLICT DO NOTHING`, so concurrent requests cannot both claim the same token and Valkey loss cannot erase the replay record. A same-IP duplicate inside the short grace period is rejected without revoking the first request's chain; it never receives another descendant. Other reuse revokes the chain. Expired claim rows are removed by a daily bounded cleanup task. Covered by the JTI unit tests and real PostgreSQL integration tests, including replay after deleting any legacy Valkey marker.

---

## Revocation is version-based: one durable Postgres version bump, not a token registry to iterate

1. Every access and refresh token embeds the account's `account_ver` and its own chain's `chain_ver` at mint time (`jwt_service.py`). `verify_token` and `refresh_tokens()` compare those values with durable Postgres records; Valkey is only a best-effort cache.
2. A whole-account revoke (`POST /auth/logout/all`, password reset confirm, self/protected password change, forced deactivation/purge) is one `bump_account_version` call. One atomic Postgres upsert increment makes every device's access and refresh tokens fail on their next use, with no per-token iteration.
3. A single-session revoke (logout, a targeted Manage Sessions "End session", or chain-scoped reuse containment above) is the equivalent durable Postgres `bump_chain_version`, scoped to one chain.

**What this replaced**: a design that tracked every live refresh-token `jti` in a per-user Valkey Hash (to revoke by iterating it) plus a separate "access tokens issued before this timestamp are dead" epoch key for access tokens specifically.

1. That epoch mechanism had a real, self-inflicted bug: PyJWT truncates a `datetime`-valued `iat` claim to whole seconds while encoding, but the epoch itself kept full sub-second precision. So a token minted the moment *after* a revoke (e.g. logging back in immediately after logout-all, trivially easy since the two calls are naturally back-to-back) could still decode to an `iat` numerically *less* than the epoch, and come back rejected as if it predated a revocation it actually postdated.
2. The fix at the time (encoding `iat` as a raw float instead of a `datetime`, preserving real ordering) is now moot: the version-based comparison this section describes is a plain integer equality check with no timestamp precision involved at all, so that whole class of bug can't recur. See `tests/backend/mystic_auth/unit/auth/token_logic/test_jwt_service_unit.py`.

---

## OAuth2 CSRF and account-hijacking protections

- **State + PKCE**: a random `state` (Valkey + cookie, validated on callback, single-use via atomic `GETDEL`) plus PKCE (S256), exceeding the minimum CSRF protection a plain OAuth2 `state` parameter alone would provide.
- **`email_verified` is load-bearing**: an OAuth2 login is only trusted if Google's own `email_verified` flag is true. This is the *only* proof of address ownership the flow relies on.
- **Pre-registration hijack window**: if an attacker signs up with a victim's email (password-based, unverified) before the victim ever does, and the victim later authenticates via Google with that same address, the pre-existing account's password is cleared at that moment. Without this, the attacker's chosen password would remain valid on an account Google has now confirmed belongs to someone else. See [Google OAuth2 / PKCE](../authentication/oauth2-pkce.md) for the full walkthrough.
- **Redirect URI is server-side fixed**, never client-influenced, ruling out open-redirect-via-OAuth.

---

## The signup/OAuth2 email race

1. `user_crud.get_by_email` (existence check) and `user_crud.create` are not wrapped in a single atomic transaction in either `signup_service.py` or `oauth2_service.py`, so a TOCTOU race between two concurrent requests for the same new email is theoretically possible at the application level.
2. The database closes it with a **unique constraint** on `users.email`, so the loser gets an `IntegrityError`.
3. Both call sites catch broad exceptions, log, and return a clean failure (`False` or `None`) that the handler turns into the standard generic error response.

---

## Self-service password change requires the current password

1. `PUT /users/me` (self-service profile update) requires `current_password`, verified against the account's existing `hashed_password`, whenever the request also sets a new `password`.
2. Without this, a hijacked `access_token` cookie (e.g. via XSS) was enough to permanently lock the legitimate owner out: the attacker just sets a new password, no proof of the old one required, and the existing "password change revokes all sessions" behavior (see [../database/design.md](../database/design.md)) would then work *against* the real owner by killing their session too.
3. **Skipped** when the account has no password yet (`hashed_password is None`, an OAuth-only account setting a password for the first time): there's nothing to confirm against, and requiring one would make it impossible for such an account to ever add a password.
4. The protected account route (`PUT /users/{email}`, which reuses the same `UserUpdate` schema) does **not** require this, since a caller changing someone else's password already authenticated via their own `users:update_any` permission; requiring the *target's* current password there would be nonsensical and isn't what the check is protecting against.

See `backend/mystic_auth/api/user_routes/user_self_service_routes.py::update_my_profile` and `tests/backend/mystic_auth/integration/user/test_user_self_service_routes_integration.py` (`test_self_password_change_requires_current_password`, `test_self_password_change_rejects_wrong_current_password`, `test_setting_a_first_password_on_an_oauth_only_account_does_not_require_current_password`) and `test_user_account_lifecycle_integration.py` (`test_admin_password_change_does_not_require_admins_current_password`).

---

## Logout and logout-all are idempotent about an already-dead refresh token

1. **The old behavior**: `POST /auth/logout` and `POST /auth/logout/all` previously treated "the presented refresh token is already revoked/expired/malformed" as an error (`400`), without clearing cookies.
2. **Why that was a real problem, not just an edge case**: this was reachable through a completely legitimate path, not just an attacker replaying a stale token. A self-service or permission-protected password change (see below) revokes *every* refresh token for the account, including the one the current browser is still holding. So clicking Logout right after a "password updated" toast presented that now-dead token, got a `400 Invalid refresh token or already revoked`, and was left looking still logged in with stale cookies the client had no way to clear itself (`setupAuthInterceptor.ts` only acts on `401`, and `useLogoutMutation`'s `onSuccess`, the only place that clears the Zustand auth store, never fires on a mutation error).
3. **The fix**: both handlers now treat this as a success instead. The caller's actual goal, no valid session left in this browser, is already true whether or not the presented token was still live to revoke, so both always clear cookies and return `200`.
   - `logout/all` specifically switched from `jwt_service.verify_token` (which refuses to return anything for an already-revoked token) to `jwt_service.decode_payload` (which skips the revocation check, same as reuse-detection in `refresh_token_service.py`), so it can still resolve the owning email and revoke whatever sessions remain elsewhere, while still enforcing the token's `type` claim, so a wrong-type token (e.g. an access token mistakenly presented as the refresh cookie) is never treated as resolving a real session.
   - The security audit trail is unaffected by the response-code change: both handlers still record `success=False` for an already-dead/undecodable token (and, for `logout/all`, `user_email=None` when no email could be recovered at all), so a real operator reviewing the log can still tell the two cases apart even though the caller-facing outcome looks identical.
4. **Scope of the idempotency**: this is specifically about an already-dead *presented token*, not about whether the revoke Valkey was asked to perform actually happened.
   - `logout/all` is the one exception to "always `200`": if the account-version bump itself can't be confirmed (Postgres unavailable), it returns `503` instead, since unlike an already-dead token (nothing left to revoke, goal already met) an unconfirmed bump means the revoke genuinely didn't happen.
   - Plain `logout` keeps returning `200` even then, since ending this one browser's own session is its actual goal regardless of the wider account state. See [Session Management: bump failure handling](../authentication/session-management/token-lifecycle.md#bump-failure-handling).
5. **Also covered**:
   - The permission-protected path, not just self-service: a caller changing a *different* account's password (`PUT /users/{email}`) revokes that target's sessions, so the target's own browser is the one left holding a dead refresh-token cookie; logging out from the target's session must succeed the same way.
   - A malformed (not just merely-revoked) cookie value.
   - Two logout calls presenting the identical already-used token back to back (e.g. two tabs, or a retried request): both must succeed rather than only the first.

See `backend/mystic_auth/auth/logout/logout_handler.py`, `backend/mystic_auth/auth/logout_all/logout_all_handler.py`, `tests/backend/mystic_auth/unit/auth/logout/test_logout_handler_unit.py`, `tests/backend/mystic_auth/unit/auth/logout_all/test_logout_all_handler_unit.py`, and `tests/backend/mystic_auth/integration/user/test_user_self_service_routes_integration.py` (`test_logout_after_self_password_change_still_succeeds_and_clears_cookies`, `test_logout_all_after_self_password_change_still_succeeds_and_clears_cookies`, `test_repeated_logout_calls_with_the_same_token_both_succeed`, `test_logout_with_malformed_refresh_token_cookie_still_succeeds_and_clears_cookies`, `test_logout_all_with_malformed_refresh_token_cookie_still_succeeds_and_clears_cookies`) and `test_user_account_lifecycle_integration.py` (`test_logout_after_admin_password_change_for_another_user_still_succeeds_and_clears_cookies`).

---

## Rate limiting and lockout are layered, not singular

1. Login has **both** a generic sliding-window rate limiter (per-IP and per-account) and a separate, purpose-built brute-force lockout service with its own thresholds (`MAX_FAILED_LOGIN_ATTEMPTS` / `MAX_FAILED_LOGIN_ATTEMPTS_PER_IP`).
2. The two serve different purposes:
   - The rate limiter caps *request volume* generically (applied to all 10 routes in `auth_routes.py`: signup, login, OAuth2 login/callback, `/auth/me`, logout, logout-all, password-reset request/confirm, verify-account).
   - The lockout service specifically tracks *failed authentication attempts* and can lock an account/IP out even if each individual request was well within the rate limit.
3. `POST /auth/refresh/` is deliberately **not** rate-limited by this mechanism: the refresh flow already has its own protection via single-use token rotation and reuse detection (see above), which a generic request-volume limiter would only duplicate. See [Login](../authentication/login.md).

---

### Rate limiter fails closed on a Valkey outage: reviewed, kept intentionally

1. `RateLimiterService.record_request` (`auth/security/rate_limiting/rate_limiter_service.py`) catches every Valkey exception and returns `False` ("not allowed").
2. Because all 10 rate-limited routes depend on this, a Valkey outage makes every one of them reject every caller: a full, if temporary, authentication-surface outage, not just degraded rate limiting.
3. Most routes surface that as a JSON `429`; the two OAuth2 routes (`oauth2_login`/`oauth2_callback`) redirect to `/login?error=TOO_MANY_ATTEMPTS` instead, via `rate_limited`'s `redirect_url` param, since they're top-level browser navigations with nowhere sensible to render a JSON body.

---

**This was reviewed and kept as-is, deliberately.**

1. The alternative, fail *open* (treat a Valkey outage as "unlimited," letting every request through unthrottled), would silently disable brute-force and credential-stuffing protection across the entire authentication surface at precisely the moment (infrastructure instability) an attacker is statistically most likely to be probing for exactly that kind of gap.
2. A temporary full-surface `429` is recoverable and visible (users see errors, monitoring/alerting on 429 rates would catch it); a temporary silent removal of all rate limiting is neither.
3. For a template whose purpose is an authentication *foundation*, fail-closed is the safer default to ship.

This is a genuine availability/security tradeoff, not a free resolution either way: a deployment with different priorities (e.g. one that treats any auth downtime as worse than degraded brute-force protection, because Valkey outages are rare and monitored separately) can override it by changing `record_request`'s `except` clause to return `True` instead. That should be a deliberate, reviewed change for that specific deployment, not this template's default.

---
