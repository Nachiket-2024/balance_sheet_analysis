# Testing Overview

## Backend: pytest

Config: `pytest.ini` (repo root): `testpaths = tests/backend`, `addopts = -v --cov=backend/app --cov=backend/mystic_auth --cov-report=html`. Coverage is measured and an HTML report generated (`htmlcov/`) on every invocation. **`--cov-fail-under` is deliberately not set in `pytest.ini`**: it would apply to every invocation, including partial local runs (`pytest tests/backend/mystic_auth/unit` alone covers only a slice of `backend/mystic_auth` and would false-fail well under any sensible whole-project threshold). CI enforces an 85% cumulative-coverage gate once instead: see below.

| Suite | Path | Covers |
|---|---|---|
| App wrapper | `tests/backend/app/` (1 file) | The thin `backend/app/` wrapper itself: the global exception handler wired up in `app/main.py` |
| Unit | `tests/backend/mystic_auth/unit/` (49 files, in feature subfolders: `auth/`, `authorization/`, `api/`, `logging/`, `scripts/`, `taskiq_tasks/`, `audit_log/`, `error_monitoring/`, `core/`, `user_crud/`: mirroring `backend/mystic_auth/`'s own layout) | Auth (login/signup/logout/refresh/password reset/JWT/OAuth2/account verification), authorization (service, cache, dependency, evaluator, condition validator/schema consistency, policy routes/history/repository caching), rate limiter, login lockout, correlation ID middleware, security headers, route helpers, logging config (including the startup-vs-routine logger split), email tasks, user email CRUD, error monitoring (`sentry_service` init/capture, conditional on `SENTRY_DSN`; the global exception handler's report-then-500 behavior), `Settings` (ignores env vars it doesn't declare: see [Security Decisions](../security/decisions.md)) |
| Integration | `tests/backend/mystic_auth/integration/` (8 files) | Audit log, authorization routes, auth API, health, OAuth, security audit log, security headers, user routes: real DB/Redis, real HTTP client |
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

# Inside the Docker network (avoids host/container Postgres port conflicts :
# see PBAC Troubleshooting). --user root: needed on native Linux, or pytest-cov's
# coverage output crashes with a PermissionError: see
# docs/mystic_auth/docker/overview.md#running-a-one-off-command-inside-a-container,
# which also covers a separate Windows/Git-Bash-only "Cwd must be an
# absolute path" failure if you hit that instead.
docker compose exec --user root -w /repo backend python -m pytest tests/backend/
```

CI (`.github/workflows/ci.yml`) runs the app-wrapper, unit, integration, and security suites against GitHub Actions service containers (Postgres 15, Redis 7) on every push/PR to `main`: `tests/backend/app` and `tests/backend/mystic_auth/unit` run together as one step/coverage base. The integration and security steps pass `--cov-append` so coverage accumulates across all steps, and the security step (running last) adds `--cov-fail-under=85`: a regression alarm against *cumulative* unit+integration+security coverage (currently ~91%), not any single suite in isolation. Performance tests also run in CI, as a **non-blocking** (`continue-on-error: true`) informational step: their thresholds are deliberately generous regression alarms rather than a strict SLA, but timing can still be noisier on shared runners than locally, hence non-blocking rather than a hard gate.

## Frontend: Vitest

Config: `frontend/vitest.config.ts`: tests physically live in `tests/frontend/` (outside `frontend/src/`) via a custom Vite resolver plugin, not co-located with source. Coverage provider `v8`, reporters `text`/`json`/`html`: same as the backend. `coverage.thresholds` (statements 85 / branches 78 / functions 79 / lines 86: a few points below the current whole-project average of ~89/82/84/90%) are enforced, but **only when coverage is actually collected** (`vitest run --coverage`, i.e. the `test:coverage` script): plain `vitest run` (`npm run test`) never evaluates them on its own, which is why CI runs `test:coverage` specifically (see below).

| Suite | Path | Covers |
|---|---|---|
| App wrapper | `tests/frontend/app/` (1 file) | Routing declared in `frontend/src/app/App.tsx` |
| Unit | `tests/frontend/mystic_auth/unit/` (~32 files) | API clients (`auth`/`users`/`profile`/`policies`/`audit` endpoints, `apiError`, the refresh interceptor), `useAuthSession`, `Authorized`/`ProtectedRoute`/`Sidebar`/`Navbar`/`AppLayout`, `useAuthorization`/`useCan`/`authorizationService` (PBAC layer), `passwordRules`/`PasswordRulesChecklist`, `useUnsavedChangesWarning`, `themeStore`, `ui/*` (`DataTable`, `ConfirmDialog`, `FormAlert`, `LoadingState`, `Toaster`, `ErrorBoundary`: including that it reports the caught error), `errorMonitoring` (conditional on `VITE_SENTRY_DSN`) |
| Integration | `tests/frontend/mystic_auth/integration/` (9 files) | Audit log page, auth flow, dashboard, login page, password policy consistency, PBAC authorization flow, policies page (list, permission gating, create/edit/delete, conditions-JSON validation, unsaved-changes discard prompt), users page (list, permission gating, delete/purge/reactivate/role-change, assign/revoke via the Policies dialog), profile page (including the self-service current-password requirement) |

**Running:**

```bash
npm run typecheck --prefix frontend   # three tsc --noEmit passes: app / node / test tsconfigs
npm run lint --prefix frontend        # eslint over frontend/ and tests/frontend/
npm run test --prefix frontend         # vitest run (no coverage collection/thresholds)
npm run test:coverage --prefix frontend  # vitest run --coverage (thresholds enforced)
```

CI runs `typecheck`, `lint`, `test:coverage` (not plain `test`: see above), and `build` on every push/PR to `main`.

### `.not` chaining and jest-dom/Vitest type augmentation

`frontend/tsconfig.test.json` goes to some length (see its own inline comments) to make jest-dom's Vitest matcher augmentation (`toBeInTheDocument()`, etc.) type-check via a shared module-identity `paths` mapping. That augmentation does not currently extend to chained `.not.toBe()`/`.not.toBeNull()`: `tsc` reports `Property 'not' does not exist` for those specific chains even though the same assertions type-check fine unchained. No test in this repo uses `.not.` chaining as a result; prefer a positive assertion instead (`toBeTruthy()`, an equality check phrased the other way round, etc.): see `tests/frontend/mystic_auth/unit/layout/AppLayout.test.tsx` and `tests/frontend/mystic_auth/unit/ui/LoadingState.test.tsx` for examples.

## Troubleshooting

- **A test hangs / can't connect to Postgres from the host**: see [PBAC Troubleshooting: database connection issues](../authorization/troubleshooting.md#database-connection-issues): a native Postgres install or another project's container on the host can still intercept whatever port is configured, even though this template maps Postgres to the non-default host port `5433` specifically to avoid the common case.
- **Frontend test can't resolve a `tests/frontend/...` import**: confirm `frontend/vitest.config.ts`'s custom resolver plugin is active: it's what makes the split `frontend/src` / `tests/frontend` layout work; running vitest from anywhere other than `frontend/` bypasses it.
