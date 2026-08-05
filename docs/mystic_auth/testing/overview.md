# Testing Overview

---

## Backend: pytest

Config lives in `pytest.ini` at the repo root. It sets
`testpaths = tests/backend` and collects coverage for `backend/app` and
`backend/mystic_auth`. An HTML report is generated in `htmlcov/` on every run.
`--cov-fail-under` is not set in `pytest.ini` because it would also apply to
partial local runs. CI enforces the 85% cumulative coverage gate after unit,
integration, and security tests append to the same coverage data.

| Suite | Path | Covers |
|---|---|---|
| App wrapper | `tests/backend/app/` (1 file) | The thin `backend/app/` wrapper itself: the global exception handler wired up in `app/main.py` |
| Unit | `tests/backend/mystic_auth/unit/` (62 files, feature subfolders mirror `backend/mystic_auth/`) | Auth flows, authorization service/evaluator/cache, condition validation, policy routes/history/repository caching, rate limiting, lockout, middleware, security headers, route helpers, logging config, email tasks, user CRUD, ORM/schema coverage, database and Redis singletons, error monitoring, session events, and `Settings` behavior |
| Integration | `tests/backend/mystic_auth/integration/` (16 files plus shared account helpers) | Audit log, policy CRUD, policy assignment, authorization checks, auth flows, health, manage sessions, OAuth, security headers, user self-service, user list/update, and account lifecycle against real DB/Redis and a real HTTP client |
| Security | `tests/backend/mystic_auth/security/` (5 files) | Batch authorization abuse, context spoofing, invalid condition payload, policy tampering, privilege escalation |
| Performance | `tests/backend/mystic_auth/performance/` (1 file) | Authorization performance |

**Running:**

```bash
# From repo root, against local Postgres/Redis (see .env)
python -m pytest tests/backend/app -q
python -m pytest tests/backend/mystic_auth/unit -q
python -m pytest tests/backend/mystic_auth/integration -q
python -m pytest tests/backend/mystic_auth/security -q
python -m pytest tests/backend/mystic_auth/performance -q

# Inside the Docker network. This avoids host/container Postgres port conflicts.
# scripts/docker/backend-exec.sh (or .ps1/.cmd) wraps the --user root and
# MSYS_NO_PATHCONV workarounds this needs. See
# docs/mystic_auth/docker/overview.md#running-a-one-off-command-inside-a-container.
scripts/docker/backend-exec.sh python -m pytest tests/backend/
```

CI (`.github/workflows/ci.yml`) runs app-wrapper, unit, integration, and
security suites against GitHub Actions service containers (Postgres 15, Redis 7)
on every push and pull request to `main`. App-wrapper and unit tests create the
first coverage base. Integration and security tests pass `--cov-append`, so the
security step can enforce the cumulative `--cov-fail-under=85` gate. Performance
tests also run as non-blocking informational checks because timing is noisy on
shared runners.

---

## Frontend: Vitest

Config lives in `frontend/vitest.config.ts`. Tests live in `tests/frontend/`
outside `frontend/src/`, wired through a custom Vite resolver plugin. Coverage
uses the `v8` provider with `text`, `json`, and `html` reporters. Thresholds are
enforced only by `vitest run --coverage`, so CI runs `test:coverage`.

| Suite | Path | Covers |
|---|---|---|
| App wrapper | `tests/frontend/app/` (1 file) | Routing declared in `frontend/src/app/App.tsx` |
| Unit | `tests/frontend/mystic_auth/unit/` (~36 files) | API clients, refresh interceptor, auth/session hooks, SSE invalidation, authorization components and hooks, password rules, user-agent parsing, unsaved-change handling, theme store, shared UI components, error boundary reporting, and optional error monitoring |
| Integration | `tests/frontend/mystic_auth/integration/` (10 files) | Audit log page, auth flow, dashboard, login, Manage Sessions, password policy consistency, PBAC authorization flow, policies page, users page, and account settings |

**Running:**

```bash
npm run typecheck --prefix frontend   # app, node, and test tsconfigs
npm run lint --prefix frontend        # eslint over frontend/ and tests/frontend/
npm run test --prefix frontend         # vitest run (no coverage collection/thresholds)
npm run test:coverage --prefix frontend  # vitest run --coverage (thresholds enforced)
```

CI runs `typecheck`, `lint`, `test:coverage`, and `build` on every push and pull request to `main`.

### `.not` chaining and jest-dom/Vitest type augmentation

`frontend/tsconfig.test.json` uses a shared module-identity `paths` mapping so
jest-dom's Vitest matcher augmentation, such as `toBeInTheDocument()`,
type-checks reliably. That augmentation does not currently extend to chained
`.not.toBe()` or `.not.toBeNull()`. No test in this repo uses `.not.` chaining.
Prefer a positive assertion such as `toBeTruthy()` or an equality check phrased
the other way round.

---

## Troubleshooting

- **A test hangs or cannot connect to Postgres from the host:** see
  [PBAC Troubleshooting: database connection issues](../authorization/troubleshooting.md#database-connection-issues).
  A native Postgres install or another project's container can still intercept
  the configured host port.
- **Frontend test cannot resolve a `tests/frontend/...` import:** confirm
  `frontend/vitest.config.ts`'s custom resolver plugin is active. Running Vitest
  from outside `frontend/` bypasses it.
