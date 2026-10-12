# Testing Map
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

This is the canonical navigation layer for the test suite. Each focused page
maps source files to an execution boundary and explains what each test proves,
why the boundary exists, and what it does not prove. A reader should be able
to understand the test suite without opening a test file.

The counts below are source-file counts, not test-case counts. `pytest` and
Vitest can collect several cases from one file, while Playwright multiplies
each browser test by its configured projects.

---

## Test tree

The documentation is intentionally organised like the repository rather than
like a spreadsheet. Start with the execution boundary, then move to the
focused page for the test type.

### Backend

- [Backend test map](backend.md): explains the backend layers and collection
  commands.
- [Backend unit tests](backend-unit.md): 115 isolated modules, grouped by
  authentication, PBAC, users, infrastructure, and workers.
- [Backend integration tests](backend-integration.md): 48 database- and
  Valkey-backed endpoint and workflow modules.
- [Backend security and performance tests](backend-security-performance.md):
  abuse regressions, least-privilege checks, and informational timing tests.
- [Backend authorization test detail](backend-authorization.md): scenario-level
  PBAC, policy mutation, grant guard, cache, and escalation coverage.
- [Backend authentication test detail](backend-authentication.md): login,
  tokens, refresh, logout, reset, OAuth, and verification scenarios.
- [Backend users and sessions test detail](backend-users-sessions.md):
  lifecycle, permission management, export, purge, and session scenarios.

### Frontend

- [Frontend test map](frontend.md): explains the frontend layers and how the
  runners differ.
- [Frontend unit tests](frontend-unit.md): 102 MysticAuth modules plus three
  app-wrapper modules covering hooks, API clients,
  stores, components, and pure helpers.
- [Frontend integration tests](frontend-integration.md): 33 rendered page
  modules using controlled API responses, plus the app-owned Vitest tests.
- [Frontend browser E2E tests](frontend-e2e.md): all 27 Playwright specs,
  including their mocked, disposable-account, real-matrix, and live modes.
- [Frontend authorization test detail](frontend-authorization.md): exact
  client-side permission, route, mocked-matrix, and real-matrix behavior.
- [Frontend authentication test detail](frontend-authentication.md): auth
  state, forms, refresh, logout, reset, OAuth, and verification behavior.
- [Frontend page test detail](frontend-pages-test-detail.md): detailed page,
  dialog, table, filter, and browser interaction coverage.

### Tooling

- [Tooling and CI map](tooling.md): shell tests, collection rules, and the CI
  jobs that assemble the complete test suite.

---

## How to use this catalogue

1. Start with the failing test path. The first directory tells you whether the
   failure is isolated logic, a real backend boundary, a rendered frontend
   page, or a browser/deployment check.
2. Use the matching focused page for the behavior contract and security
   rationale. It lists neighboring tests that protect the same boundary.
3. Run the narrow file first, then the complete suite for that boundary. The
   commands and database isolation rules live in [Testing Overview](overview.md).

## Reverse lookup: behavior or source to enforcing tests

The focused pages are the forward map (test file → behavior). Use this index
when starting from a behavior or security property; each row names the
enforcing files and links to the page that explains their boundary and
neighbors.

| Property or behavior | Enforcing tests |
| --- | --- |
| Login account-enumeration timing must not distinguish nonexistent, unverified, or wrong-password accounts | [`unit/auth/login/test_login_service_unit.py`](backend-authentication.md#login-and-credential-safety) and [`integration/auth/test_login_security_controls_integration.py`](backend-authentication.md#login-and-credential-safety) |
| Login lockout and rate limiting must not be bypassed by concurrency or by another auth flow's failure counter | [`integration/auth/test_login_lockout_race_integration.py`](backend-authentication.md#login-and-credential-safety), [`integration/auth/test_login_security_controls_integration.py`](backend-authentication.md#login-and-credential-safety) |
| Refresh-token replay must not revive a session or revoke an unrelated chain | [`unit/auth/refresh_token_logic/test_refresh_token_unit.py`](backend-authentication.md#jwt-refresh-and-cookies), [`integration/auth/test_refresh_token_integration.py`](backend-authentication.md#jwt-refresh-and-cookies) |
| Untrusted request context must not grant authorization | [`security/test_context_spoofing_security.py`](backend-security-performance.md#security-tests), [`unit/authorization/context/test_request_context_builder_unit.py`](backend-authorization.md#authorization-evaluation-internals) |
| A caller must not mint or assign an action/policy it cannot grant | [`security/test_permission_grant_escalation_security.py`](backend-security-performance.md#security-tests), [`security/test_privilege_escalation_security.py`](backend-security-performance.md#security-tests), [`unit/api/pbac_routes/test_policy_crud_authorization_security_unit.py`](backend-authorization.md#grant-authority-and-protected-principals) |
| Invalid conditions must fail closed and never be persisted as an evaluator bypass | [`security/test_invalid_condition_payload_security.py`](backend-security-performance.md#security-tests), [`unit/authorization/conditions/test_condition_validator_unit.py`](backend-authorization.md#authorization-evaluation-internals) |
| Restricted deployment role must not perform DDL, role administration, or become superuser | [`security/test_least_privilege_db_role.py`](backend-security-performance.md#security-tests) |
| Session fixation prevention | No dedicated test is currently named for this property. Session issuance, rotation, cookies, and replay are covered in [Backend Authentication Test Detail](backend-authentication.md), but those claims must not be read as proof of fixation resistance. Add a focused regression and index it here if the feature contract requires it. |

For a source file, follow its repository subtree to the matching focused page:
`backend/mystic_auth/auth/...` → [Backend Authentication Test Detail](backend-authentication.md),
`backend/mystic_auth/authorization/...` → [Backend Authorization Test Detail](backend-authorization.md),
and frontend source → the corresponding [frontend detail pages](frontend-authentication.md).
The page's file entry is the authoritative explanation and lists neighboring
tests for the same boundary.

---

## See also

- [Testing Overview](overview.md)
- [Backend Test Map](backend.md)
- [Frontend Test Map](frontend.md)
- [Tooling and CI](tooling.md)
