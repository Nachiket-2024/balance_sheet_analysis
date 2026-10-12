# Frontend Authorization Test Detail
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

These tests cover the client-side authorization contract. They deliberately
separate three claims: a helper computes the right answer, a rendered page
uses that answer safely, and a real browser receives the right permission set
from the backend. Only the last category crosses the frontend/backend
boundary.

---

## Permission primitives

### `tests/frontend/mystic_auth/unit/authorization/Authorized.test.tsx`

The `Authorized` cases show children when one required action is held, render
no output or an explicit fallback when it is absent, render nothing while auth
is loading, and treat an action array as “any of.” They also verify
`resourceType` is passed without changing flat permission semantics. `IfCan`
repeats the same contract through its action-oriented wrapper, including
loading, fallback, and array actions.

### `tests/frontend/mystic_auth/unit/authorization/ProtectedRoute.test.tsx`

This is the route-level fail-closed contract. It shows loading while auth is
unknown, redirects anonymous users to `/login`, redirects authenticated users
without permission to `/not-authorized`, and renders protected content for
authorized or auth-only routes. Array permissions use “any.” The final three
cases cover the dangerous permission-refresh race: dropping permissions first
shows loading rather than an immediate dashboard bounce, a confirmed loss
redirects to `/dashboard`, and a refetch proving the permission was not really
lost leaves the user on the page.

### `tests/frontend/mystic_auth/unit/authorization/useAuthorization.test.tsx`

Verifies the hook exposes the profile and permissions from the auth store,
returns true only for held actions, treats arrays as “any,” ignores
`resourceType` because the client stores a flat list, fails closed while
unauthenticated or empty, and can drive conditional rendering in a component.

### `tests/frontend/mystic_auth/unit/authorization/useCan.test.tsx`

Verifies single-action true/false results, empty and absent permission safety,
array “any” behavior, ignored resource type, and that `useAuthorized` is the
same contract for a single permission.

### `tests/frontend/mystic_auth/unit/authorization/authorizationService.test.ts`

Verifies a single check is sent as a one-item batch, resource instances are
forwarded for ownership/attribute conditions, batch results preserve order,
and the self-policy and self-audit APIs use the correct GET routes. It also
proves 401, 403, 422, and 500 responses are rejected rather than swallowed.

### `tests/frontend/mystic_auth/unit/authorization/destructiveActions.test.ts`

Verifies only fully resource-prefixed destructive actions are classified as
destructive. Bare verbs, reversible actions, and ordinary reads/writes remain
non-destructive so the UI does not over-confirm harmless operations.

### `tests/frontend/mystic_auth/unit/authorization/grantability.test.ts`

Verifies a caller must hold every built-in action and every custom business
action in a policy before the UI presents that policy as grantable.

---

## Rendered PBAC integration

### `tests/frontend/mystic_auth/integration/authorization/pbac_authorization_flow.test.tsx`

The first scenario logs in a user with a restricted permission set and proves
only the allowed UI is rendered. The second adds the required management
permission and proves protected UI becomes available. The failed-login scenario proves a
later-resolving session query cannot briefly reveal protected content. This is
mocked-backend page behavior, not proof that the server granted the permission.

---

## Mocked browser matrix

### `tests/frontend/mystic_auth/e2e/authorization/permission_matrix_browser.spec.ts`

The nine mock profiles exercise protected routes and controls using synthetic
`/auth/me` responses. The first test checks usable authorization routes and controls;
the second opens available dialogs and checks Escape restores focus. This is
the broad UI-shape matrix: it is useful for many combinations but cannot find
a mismatch between database grants and `/auth/me`.

---

## Real-account browser matrix

### `tests/frontend/mystic_auth/e2e/authorization/permission_matrix_real_accounts_browser.spec.ts`

Each of the 32 buckets logs in with a seeded account in Chromium desktop, reads `/auth/me`, and
compares the exact permission set to the policy/direct-grant expectation in
the fixture. It then checks users, policies, permissions, and rate-limit route
gates, with retry handling for the browser cookie-commit race.

The audit-log checks distinguish two independent permissions. The Authorization
decisions category shows the “All users” tab only with `policies:read`. After
switching to Security Events, the “All users” tab is checked against
`security_audit:read`. The p4 bundle supplies `policy_maintainer`,
`security_audit_access`, and `user_lifecycle`, so the
new Security Events frontend gate is exercised by real backend accounts.

The seed creates 40 role/policy/direct-grant combinations with a variable
number of disposable copies per combination. Only verified-active
representatives are browser-login buckets. The status plan intentionally
leaves unverified and deactivated accounts for backend/lifecycle coverage.
`system_superuser` is not added to this ordinary account matrix.

---

## Related page-level gates

- `tests/frontend/mystic_auth/integration/audit_log/audit_log_page.test.tsx`
  verifies category, scope, filter, loading, error, empty, and details states
  with mocked audit data.
- `tests/frontend/mystic_auth/integration/policies/policies_page_status_and_delete.test.tsx`
  verifies protected-policy status and deletion controls.
- `tests/frontend/mystic_auth/integration/users/users_page_access_dialog_self_protection.test.tsx`
  verifies the current operator cannot remove their own protective access.
- `tests/frontend/mystic_auth/integration/rate_limits/rate_limits_page.test.tsx`
  verifies the rate-limit page's permission gate alongside data states.
- `tests/frontend/mystic_auth/e2e/users/users_page_browser.spec.ts` verifies
  user-page permission gates and escaped content in a real browser.
- `tests/frontend/mystic_auth/e2e/policies/policies_page_browser.spec.ts`
  verifies policy-page route and control gating in a real browser.
- `tests/frontend/mystic_auth/e2e/permissions/permissions_page_browser.spec.ts`
  verifies permission-catalog route and details gating in a real browser.
- `tests/frontend/mystic_auth/e2e/rate_limits/rate_limits_page_browser.spec.ts`
  verifies rate-limit route and reset-control gating in a real browser.

---

## Coverage boundary

Frontend authorization tests prove client rendering and navigation. Backend
authorization tests prove enforcement and persistence. The real-account matrix
is the only listed frontend authorization test that compares a live backend
permission set to the expected seeded grants and then checks browser gates
against that same session.

See [Backend Authorization Test Detail](backend-authorization.md) for the
server-side decision, grant, cache, concurrency, and security scenarios.

---

## See also

- [Frontend Test Map](frontend.md)
- [Frontend Unit Tests](frontend-unit.md)
- [Frontend Integration Tests](frontend-integration.md)
- [Frontend Browser E2E Tests](frontend-e2e.md)
- [Backend Authorization Test Detail](backend-authorization.md)
