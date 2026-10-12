# Frontend Test Map
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

Frontend tests are divided by how much of the browser application they render.
Unit tests isolate one client-side rule or component. Integration tests render
a page and control its API responses so loading, error, empty, permission, and
success states can be deterministic. Playwright tests render the built
application in a real browser and add navigation, focus, keyboard, responsive,
and deployment behavior.

The detailed file catalogue is split into [unit tests](frontend-unit.md),
[integration tests](frontend-integration.md), and [browser E2E tests](frontend-e2e.md).
This page explains the boundaries and how they relate to backend coverage.

For the permission system specifically, [Frontend Authorization Test
Detail](frontend-authorization.md) describes the exact helper, route, mocked
matrix, and real-account assertions.

The corresponding detail pages are [Frontend Authentication Test
Detail](frontend-authentication.md) and [Frontend Page Test Detail](frontend-pages-test-detail.md).

---

## App-owned tests

The three Vitest files under `tests/frontend/app/` cover the thin application
wrapper: route selection, legal pages, and status/not-found/not-authorized
pages. The three app-owned Playwright files under `tests/frontend/app/e2e/`
verify the same public shell in a real browser.

These tests protect the boundary between the host application and the
`mystic_auth` feature. They do not prove MysticAuth backend authorization.

---

## Unit tests

The 101 files under `tests/frontend/mystic_auth/unit/` cover API request
construction, auth state, PBAC visibility helpers, audit-log presentation,
stores, theme behavior, shared controls, and small page helpers. They should
be used for a single rule such as “this control is hidden without a
permission” or “this API client sends this query shape.”

See [Frontend Unit Tests](frontend-unit.md) for each directory and source file.

---

## Integration tests

The 33 files under `tests/frontend/mystic_auth/integration/` render complete
pages or meaningful page sections with mocked API responses. They prove how
the frontend combines queries, loading states, error states, dialogs, tables,
navigation, and permission gates. Because the server is mocked, they do not
prove that the backend would grant the permission.

The app-owned Vitest files are also described on the [Frontend Integration
Tests](frontend-integration.md) page because they exercise rendered app
boundaries, even though they live outside the MysticAuth integration tree.

---

## Browser E2E tests

The 27 Playwright specs verify user-visible behavior in a real browser. Most
use mocked API responses to make UI behavior repeatable. The login/logout flow
uses a disposable account. The real permission-matrix spec uses seeded
accounts and checks `/auth/me`, route gates, authorization-log scope, and the
Security Events “All users” gate against a real backend. The live deployment
smoke is opt-in.

See [Frontend Browser E2E Tests](frontend-e2e.md) for the backend mode,
purpose, and coverage boundary of every spec.

---

## Frontend and backend coverage together

The frontend tests prove what a user sees and what requests the browser makes.
The backend tests prove that a request is allowed or denied and that state is
stored safely. Permission-gated UI should normally have a focused frontend
unit or integration test, a browser test where interaction or routing matters,
and backend authorization coverage for the enforcement boundary. The real
permission matrix is the bridge for seeded-account end-to-end checks.

---

## See also

- [Frontend Unit Tests](frontend-unit.md)
- [Frontend Integration Tests](frontend-integration.md)
- [Frontend Browser E2E Tests](frontend-e2e.md)
- [Frontend Browser E2E Tests](frontend-e2e.md)
- [Testing Map](README.md)
- [Testing Overview](overview.md)
