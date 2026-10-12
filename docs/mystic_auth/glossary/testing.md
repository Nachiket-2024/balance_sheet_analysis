# Glossary: Testing
---

Test suites, tooling, and terminology used across the backend (pytest) and frontend (Vitest) test setups. See [Glossary](README.md) for the full index, and [Testing Overview](../testing/overview.md) for the full breakdown.

---

## unit test

A test that exercises one small piece of code in isolation (a function, a service method) without a real database, Valkey, or HTTP server behind it, typically using mocks/stubs for anything external. The largest suite on both backend and frontend. See [Testing Overview](../testing/overview.md).

---

## integration test

A test that exercises a real flow end to end against real dependencies (a real Postgres database, real Valkey, a real HTTP test client), rather than mocking them out. This is what catches bugs that only show up when the pieces actually talk to each other. See [Testing Overview](../testing/overview.md).

---

## security test suite

A dedicated backend test suite (`tests/backend/mystic_auth/security/`) specifically targeting abuse scenarios: batch authorization abuse, context spoofing, invalid condition payloads, policy tampering, privilege escalation, and (opt-in) least-privilege database role checks. See [Testing Overview](../testing/overview.md).

---

## performance test

A backend suite (`tests/backend/mystic_auth/performance/`) that measures authorization timing. It runs in CI as a non-blocking, informational check rather than a hard gate, since timing is noisy on shared CI runners. See [Testing Overview](../testing/overview.md).

---

## mock / stub

A fake stand-in for a real dependency (an external API call, a database, a Google HTTP request) used in a unit test so the test doesn't actually need that dependency to be live. The OAuth2 unit tests, for example, mock the real calls to Google. See [OAuth2 / PKCE: Testing coverage](../authentication/oauth2-pkce.md#testing-coverage).

---

## fixture

Reusable setup code a test suite depends on, such as a helper that creates a test account or a teardown step that cleans up rows after each test. Shared fixtures used across a split group of test files are factored into their own sibling module (e.g. `user_test_accounts.py`) rather than a directory-wide `conftest.py`, so their scope doesn't silently widen. See [Testing Overview: File length](../testing/overview.md#file-length).

---

## conftest.py

Pytest's special file for fixtures and setup shared across a test directory. This app's root `tests/backend/conftest.py` redirects the database connection to a dedicated `mystic_auth_test` database, so tests never run against your real dev data. See [Testing Overview: Dedicated test database](../testing/overview.md#dedicated-test-database).

---

## coverage / coverage gate

Coverage measures what percentage of the codebase's lines actually ran during the test suite. A coverage gate fails the build if that percentage drops below a set threshold (90% here), calculated cumulatively across the unit, integration, and security suites via `--cov-append`. See [Testing Overview](../testing/overview.md).

---

## smoke test

A quick, shallow check that the app actually boots and responds, not a thorough correctness check. CI's `docker-build` job builds the runtime images, boots the dev stack, and smoke-tests it before anything more thorough runs. See [CI/CD Overview](../cicd/overview.md).

---

## test database

A separate, dedicated database (`mystic_auth_test` locally, `mystic_auth_ci` in CI) that backend tests run against instead of the real dev/prod database, so test teardown (which deletes rows) never collides with real data or a live dev server's own background worker. See [Testing Overview: Dedicated test database](../testing/overview.md#dedicated-test-database).

---

## pytest

The Python test runner and framework the backend test suites are written in. Configured via `pytest.ini` at the repo root.

---

## Vitest

The JavaScript/TypeScript test runner the frontend test suites are written in, built on top of Vite. Configured via `frontend/vitest.config.ts`.

---
