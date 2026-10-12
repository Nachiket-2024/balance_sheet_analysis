# Backend Authentication Test Detail
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

This page describes authentication as a state machine: account discovery,
credential verification, token issuance, cookie/session state, refresh and
replay handling, logout, password reset, OAuth, and verification. The unit
tests isolate timing and token decisions; the integration tests prove the
same rules across HTTP, Postgres, and Valkey.

---

## Login and credential safety

- `tests/backend/mystic_auth/unit/auth/login/test_login_service_unit.py`
  proves nonexistent, unverified, OAuth-only, wrong-password, and deactivated
  accounts all follow safe credential-comparison and denial paths. It also
  proves a valid verified account succeeds and missing credentials do not cause
  an unnecessary hash comparison.
- `unit/auth/login/test_login_handler_unit.py` verifies login orchestration,
  cookie creation, generic errors, lockout responses, session creation, and
  audit outcomes returned by the handler.
- `unit/auth/login/test_auth_schemas_unit.py` verifies input normalization and
  validation before the service is called.
- `unit/auth/security/test_client_ip_unit.py` verifies trusted-proxy client-IP
  resolution. `test_login_protection_unit.py` verifies account/IP counters,
  thresholds, lockout, and recovery. `test_rate_limiter_unit.py` verifies
  fixed-window decisions, retry metadata, and unavailable-Valkey behavior.
- `integration/auth/test_login_integration.py` verifies signup-to-verification-
  to-login session issuance and that `/auth/me` exposes the user's effective
  permissions.
- `integration/auth/test_login_lockout_race_integration.py` verifies a
  concurrent failed-login burst cannot bypass lockout accounting.
- `integration/auth/test_login_security_controls_integration.py` verifies
  lockout, generic errors, rate limiting, and security audit records together
  through the real endpoint.

The important negative contract is that account existence, verification state,
OAuth-only state, and password correctness do not create distinguishable
login responses or timing shortcuts.

The related abuse contract is that failed-login counters and rate limits must
not be bypassed by concurrent requests, alternate authentication flows, or a
successful login before the configured recovery rule. A locked account/IP
must never receive a successful login response, and a denied request must not
leak policy or credential-state detail.

---

## JWT, refresh, and cookies

- `unit/auth/token_logic/test_jwt_service_unit.py` verifies access/refresh type
  tags, `iat`, account and chain versions, issuer/audience algorithm allowlists,
  expected-type enforcement, expiry, and verification-token expiry defaults.
- `unit/auth/token_logic/test_jwt_service_jti_revocation_unit.py` verifies
  JTI lookup/claiming, minimum TTL, missing email handling, replay rejection,
  account-wide and chain-scoped version bumps, timestamp/IP markers, benign
  duplicate refresh detection, malformed markers, and Valkey failure safety.
- `unit/auth/token_logic/test_token_cookie_handler_unit.py` verifies secure
  cookie attributes, matching auth paths, clearing, and environment behavior.
- `unit/auth/token_logic/test_token_version_store_unit.py` verifies account and
  chain version reads/writes used to invalidate tokens.
- `unit/auth/refresh_token_logic/test_refresh_token_unit.py` verifies valid
  rotation, malformed/wrong issuer/audience/type rejection, missing chain or
  email handling, pre-chain versus chain-scoped replay revocation, same-IP duplicate rejection without token branching, and garbage-token decoding.
- `unit/auth/refresh_token_logic/test_refresh_token_handler_unit.py` verifies
  request orchestration and refresh-cookie responses.
- `unit/auth/refresh_token_logic/test_refresh_token_valkey_unavailable_unit.py`
  verifies the fail-safe response when refresh state cannot be confirmed.
- `integration/auth/test_refresh_token_integration.py` verifies rotation,
  replay-chain invalidation, cookies, persistence, and the concurrent
  same-token double-spend rule, including rejection after legacy Valkey marker removal.

These tests distinguish cryptographic validity from revocation state. A valid
JWT is not automatically an accepted session token.

---

## Logout and session invalidation

- `unit/auth/logout/test_logout_handler_unit.py` verifies missing refresh-token
  handling, already-revoked and undecodable token behavior, both cookie paths,
  successful revocation status, and accurate audit entries including resolved
  or unavailable email.
- `unit/auth/logout_all/test_logout_all_handler_unit.py` verifies all-session
  invalidation and response/cookie behavior.
- `unit/auth/manage_sessions/test_session_revoke_handler_unit.py` verifies a
  revoke returns 503 when the chain-version bump cannot be confirmed and
  succeeds only after confirmation.
- `integration/auth/test_logout_integration.py` verifies logout and logout-all
  invalidate real sessions and clear cookies.
- `integration/user_session/test_manage_sessions_integration.py` verifies
  session listing, current-device marking, another-device revoke, audit event,
  real-time event, revoked-token scope, 503 uncertainty, current-session
  protection, 404s, cross-user denial, and logout removal.
- `integration/user_session/test_manage_sessions_concurrency_integration.py`
  verifies two concurrent revocations of one session have one winner.
- `integration/user_session/test_session_row_cleanup_integration.py` verifies
  revoke/logout/logout-all delete exactly the intended rows and purge jobs
  delete only expired rows.

---

## Password reset and password changes

- `unit/auth/password_logic/test_password_service_unit.py` verifies Argon2
  hashing is offloaded from the event loop, password verification, dummy-hash
  non-match, strength rules, reset-token round trips, and token type checks.
- `unit/auth/password_logic/test_password_reset_unit.py` verifies single-use
  Valkey storage, unknown-user non-disclosure, successful consume, invalid JWT
  short-circuiting, concurrent replay with one winner, and token restoration
  after weak/same-password/database failure with a bounded remaining TTL.
- `unit/auth/password_reset_request/test_password_reset_request_handler_unit.py`
  verifies generic reset-request responses and dispatch behavior.
- `unit/auth/password_reset_confirm/test_password_reset_confirm_handler_unit.py`
  verifies confirmation validation, token use, password update, and failures.
- `integration/auth/test_password_reset_integration.py` verifies email/reset
  request, confirmation, expiry, replay, and password-change session effects
  through the real stack.
- `integration/user/test_user_self_service_logout_after_password_change_integration.py`
  verifies password change logs out the expected other sessions.

---

## OAuth and account verification

- `unit/auth/oauth2/test_oauth2_callback_state_validation_unit.py` verifies
  state mismatch/replay rejection. `test_oauth2_login_handler_unit.py`
  verifies redirect/request construction. `test_oauth2_service_unit.py`
  verifies provider exchange, identity linking, PKCE, and duplicate identity
  decisions.
- `integration/auth/test_oauth_integration.py` verifies callback, linking,
  PKCE/state, cancellation, and duplicate-provider behavior with real requests.
- `unit/auth/verify_account/test_account_verification_service_unit.py`
  verifies atomic GETDEL consumption, already-used/wrong-type rejection,
  expiry forwarding, and when verification email is sent or skipped.
- `unit/auth/verify_account/test_account_verification_handler_unit.py`
  verifies invalid-token status, separate verification lockout namespace,
  lockout-before-mutation, generic email-request response, and send-only audit
  logging.
- `unit/auth/verify_account/test_user_verification_service_unit.py` verifies
  account verification state transitions and notification decisions.
- `integration/auth/test_signup_verify_concurrency_integration.py` verifies
  concurrent signup/verification cannot create inconsistent accounts.

---

## See also

- [Backend Test Map](backend.md)
- [Backend Unit Tests](backend-unit.md)
- [Backend Integration Tests](backend-integration.md)
- [Backend Authorization Test Detail](backend-authorization.md)
- [Testing Overview](overview.md)
