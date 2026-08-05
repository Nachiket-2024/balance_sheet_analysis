# Docker Validation History

A log of past live-verification passes against the running Docker stack: what was actually run, what it found, and what got fixed as a result. Each entry describes what was true *at the time of that pass*; it's a historical record, not current-state reference material (for that, see [Docker Overview](overview.md)). Test/file counts below are frozen at whatever they were during that specific pass, not kept in sync with the current suite.

## `user_routes.py` split: live route verification

On August 2, 2026, `backend/mystic_auth/api/user_routes/user_routes.py` (410 lines, mixing self-service and admin-tier endpoints) was split into `user_self_service_routes.py` (`GET`/`PUT /users/me`) and `user_management_routes.py` (the other seven endpoints), with `user_self_service_router` registered before `user_management_router` in `main.py` specifically to prevent the management router's `PUT /{user_email}` wildcard from shadowing `PUT /users/me` (Starlette matches routes in registration order across the whole app, not per-router).

Verified against the rebuilt, running stack rather than trusting the code read alone: `docker compose up -d --build` came up with all services healthy and `alembic upgrade head` succeeding against the new router imports; `curl http://localhost:8000/users/me` (unauthenticated) returned `401` (correctly hitting the self-service handler's auth dependency, not a 404 or a misrouted admin handler); `GET /openapi.json` confirmed all 8 original `/users/*` paths still present with the same HTTP methods. Full suite re-run inside the containers: `tests/backend/app` + `tests/backend/mystic_auth/unit` (543 passed locally), `integration` (152 passed) + `security` (`--cov-fail-under=85`, 22 passed, 92.6% actual) via `docker compose exec --user root`, and the frontend suite (263 passed) via `docker compose exec frontend npm run test`.

---

## Email worker logging, dev-up ErrorActionPreference crash, and always-fresh startup banners

On July 29, 2026, verified three related fixes against the running Docker stack:

- `send_email_task` (`backend/mystic_auth/taskiq_tasks/email_tasks.py`) switched from `get_logger` to a new `get_worker_logger` (`backend/mystic_auth/logging/logging_config.py`), and now logs `Sending email to {to_email}` before the send in addition to the existing `Email sent successfully to {to_email}`. Triggered a real password-reset request against the running stack (`curl -X POST /auth/password-reset/request`); both lines appeared live in `docker logs mystic-auth-taskiq_worker-1`, timestamped a few seconds apart around the actual SMTP round trip. `tests/backend/mystic_auth/unit/logging/test_logging_config_unit.py` and `tests/backend/mystic_auth/unit/taskiq_tasks/test_email_tasks_unit.py` (20 tests total) passed via `docker compose exec --user root -w /repo backend python -m pytest`, using the `MSYS_NO_PATHCONV=1` Git Bash workaround documented above.
- `scripts/dev-up.ps1` had `$ErrorActionPreference = "Stop"` at the top. `docker compose build`/`up` write routine progress to stderr, which PowerShell 5.1 wraps into a terminating `NativeCommandError` under `Stop`, killing the script right after the first build line and before it ever reached the log tail. Reproduced by running the script via a PowerShell background job against a torn-down stack: it died on `docker compose up -d`'s own build output. Fixed by changing to `$ErrorActionPreference = "Continue"` and relying on the script's existing explicit `$LASTEXITCODE` checks. Re-ran the same way after the fix: the script completed end-to-end and the tail showed backend/frontend/taskiq_worker startup lines correctly.
- Confirmed separately that `--since $TailSince` correctly omits a service's boot banner when that service was already running before the script's own invocation (expected `docker compose logs --since` behavior, not a bug). Added an explicit `docker compose restart backend taskiq_worker` right after `docker compose up -d` in both `dev-up.sh` and `dev-up.ps1` so the banner is fresh on every run, not just the first. Verified by re-running `dev-up.ps1` against an already-healthy stack: Uvicorn's startup lines and Taskiq's `Listening started` lines both appeared in the tail even though neither container had been recreated by `up -d` itself.

---

## Dev-up log-tail update: taskiq_worker included

On July 29, 2026, verified the dev helper log-tail update against the running Docker stack:

- `docker compose config --quiet` passed.
- `docker compose up -d` completed successfully.
- `docker compose ps --format "table {{.Service}}\t{{.Status}}"` showed `postgres`, `redis`, `bugsink`, `backend`, and `taskiq_worker` healthy; `frontend` was running as expected for dev, where it has no healthcheck.
- `docker compose logs --tail=20 backend frontend taskiq_worker` returned interleaved logs from all three tailed services, including `taskiq_worker` startup and "Listening started" lines.
- Running `.\scripts\dev-up.ps1` reached the attached tail command `docker compose logs -f backend frontend taskiq_worker`; the process was then stopped manually so the validation command did not remain attached.

---

## Full stack: initial pass

Ran `docker compose up -d --build` (dev compose) from the repo root and verified the stack end-to-end (template-preparation pass):

- All five core services (`postgres`, `redis`, `backend`, `taskiq_worker`, `frontend`) reached a running state; `postgres`, `redis`, `backend`, `taskiq_worker` all reported `healthy` on their respective healthchecks (`frontend` dev has none, by design: see [Docker Overview: Healthchecks](overview.md#healthchecks)).
- `alembic` ran the full migration chain successfully.
- `GET /health/ready` returned `{"status":"ok","checks":{"database":"ok","redis":"ok"}}`; `GET /` returned the `APP_NAME`-driven welcome message, confirming the env-driven app name reaches the running container.
- Frontend dev server responded `200` on `http://localhost:5173/`, and its `<title>` correctly resolved from `VITE_APP_NAME` via Vite's `%VITE_APP_NAME%` `index.html` substitution.
- `docker compose exec -w /repo backend python -m pytest tests/backend/mystic_auth/unit tests/backend/mystic_auth/integration tests/backend/mystic_auth/security`: all 522 tests passed.
- `npm run build` inside the `frontend` container succeeded (`tsc -b && vite build`), including after the promote-to-admin UI removal.
- Full auth surface exercised via real HTTP requests against the running stack
  with real Postgres and Redis. Covered signup, verification, login,
  `GET /auth/me`, refresh rotation, logout, password-reset request/confirm, the
  bidirectional `PATCH /users/{email}/role` endpoint, PBAC allow/deny, policy
  create/list/delete, and PBAC audit logging. The role endpoint moved a user
  from `user` to `admin` and back to `user`. The removed
  `PATCH /users/{email}/promote-to-admin` endpoint correctly returned 404.
  Google OAuth2 was verified up to the redirect. Completing the full round trip
  requires a live browser and Google consent, which was not exercised.
- `taskiq_worker` crash-looped for the first ~30 seconds against the fresh Redis Stream before self-stabilizing (`NOGROUP` error, auto-restarted by its own process-manager supervisor): no task was lost. **Update from a later QA pass**: re-investigated by reading `taskiq-redis`'s actual source and reproducing against a genuinely fresh Redis container: the race does not reproduce with the currently pinned `taskiq-redis==1.2.3` (0 restarts observed). See [Background Email Delivery](../background-workers/taskiq.md#startup-on-a-fresh-redis-instance) for the full investigation; the crash-loop described above likely reflected an older dependency version or a since-fixed detail of the worker command (the `--reload` flag mentioned in earlier notes has since been removed from the `taskiq_worker` command entirely).

`docker-compose.yml` no longer hardcodes `container_name`s or the default `5432`/`6379` host ports for `postgres`/`redis` (now `5433`/`6380`): those are the two most common local collision points (a native Postgres/Redis install, or another Compose project using the same generic names) and this template should come up cleanly next to other local projects out of the box. Containers still reach each other at `postgres:5432`/`redis:6379` over the Docker network regardless of the host mapping.

---

## Error monitoring service: live verification

Bugsink starts by default with plain `docker compose up` now: the `--profile monitoring` flag used in this section's verification notes below predates that (it was opt-in at the time). No profile flag is needed today.

`docker compose --profile monitoring up -d bugsink` was verified against a fresh
`postgres_data` volume. `docker/postgres-init/init-bugsink-db.sh` created the
separate `bugsink` database, Bugsink migrations ran cleanly, the configured
superuser was created, the container reported `healthy` (`GET /health/ready`
returned `200`), and the login page responded at `http://localhost:8010`
(`GET /` returned `302` to login). Confirmed isolated from the app's
`mystic_auth` database: both live on the same Postgres server in separate
databases.

Also verified live end to end: a real HTTP request to a temporary route that
raised an exception produced a `500` response, and the exact exception appeared
as an Issue in Bugsink within seconds. This confirms the full path from
`main.py`'s `global_exception_handler` through `capture_exception`, `sentry-sdk`,
network transport, and Bugsink ingestion. A malformed `SENTRY_DSN` was also
confirmed *not* to crash the app. See
[Security Decisions](../security/decisions.md#a-malformed-sentry_dsn-must-never-crash-the-app).

**`bugsink-seed` auto-seeding: live verification.** Ran `docker compose --profile monitoring up bugsink-seed` against a healthy `bugsink`: it created the "MysticAuth" team/project via Bugsink's own Django ORM and wrote both DSN forms into the `bugsink_dsn` volume, printing the seeded project id/key to its own log. Re-ran it a second time: same project id and key came back (no duplicate team/project created), confirming `get_or_create` idempotency. Recreated `backend`/`frontend` afterward and confirmed (via `/proc/1/environ` inside each container, since `docker exec` itself only inherits the container's baseline `env_file` config, not what the entrypoint script exports into PID 1) that both processes picked up the seeded DSN with no manual restart. A real exception triggered against that DSN showed up as an Issue under the seeded project.

Needed one fix along the way: the image runs as a non-root user that can't write into a fresh named volume, so `bugsink-seed` runs with `user: root` (it's a short-lived one-shot container, not a long-running service). A second approach: having `backend/mystic_auth/core/settings.py` itself fall back to reading the seeded file whenever `SENTRY_DSN` came back empty: was tried and reverted: it broke `tests/backend/mystic_auth/unit/core/test_settings_unit.py::test_optional_fields_default_when_unset`, correctly catching a real design flaw (a leftover seeded file from a previous `--profile monitoring` run would silently re-enable monitoring even after a user explicitly cleared `SENTRY_DSN`, contradicting this doc's own "clear the var, it's off immediately" claim above). The one-off verification command below instead sources the seeded file only for that single command, leaving the app's own "empty `SENTRY_DSN` means off" rule untouched.

---

## Image content audit: files that shouldn't ship

A pre-release audit checked what actually ends up *inside* the built images, not just whether they build. Both of the following were found by building the image and listing its real contents (`docker run --rm <image> find ...`), not by inspecting the Dockerfiles/`.dockerignore` alone:

- **`backend/logs/`** (23MB of real local access-log data: request paths, timestamps, correlation IDs) was present in a freshly built backend image with no bind mount involved. Root cause and fix: [Security Decisions](../security/decisions.md#dockerignore-previously-let-local-files-leak-into-built-images).
- **`__pycache__/` directories** were present nested throughout `backend/app/**` and `backend/mystic_auth/**` despite `.dockerignore` listing `__pycache__/`: the bare pattern doesn't recurse the way it looks like it should; fixed with explicit `**/`-prefixed patterns. Re-verified after the fix: `find /app -iname "__pycache__"` on a fresh image returns nothing. (This predates the `mystic_auth/`+`app/` split: at the time, `backend/app/` was the whole codebase; see [Security Decisions](../security/decisions.md#dockerignore-previously-let-local-files-leak-into-built-images) for the original writeup.)
- The actual production frontend image (`nginx` stage, `docker/frontend.Dockerfile --target production`) was checked separately and found clean: it only ever receives `--from=builder /app/dist`, never the full source tree where these local-artifact leaks would apply.
- **`VITE_*` env vars were silently never reaching the production bundle**: found by building the `production` target with no build args (matching what `docker-compose.local-prod.yml` did before this was fixed) and inspecting the actual output: the browser tab title baked in as the literal string `%VITE_APP_NAME%` (Vite's own build log flagged this: `%VITE_APP_NAME% is not defined in env variables`), and the compiled `axiosInstance` chunk showed `apiBaseUrl: undefined`: meaning every API call from a production build would have gone out with no base URL at all. Root cause: the `builder` stage has no bind-mounted `frontend/.env` the way the `dev` target does, and `frontend/.env` itself is `.dockerignore`d from the build context, so Vite's env loading had nothing to read from. Fixed by adding `ARG`/`ENV` for the four `VITE_*` vars to `docker/frontend.Dockerfile`'s `builder` stage and wiring them as `build.args` in `docker-compose.local-prod.yml`, sourced from the root `.env` (see [Deployment Guide](../deployment/guide.md#required-production-environment-variables)). Re-verified after the fix: with real build args supplied, the title resolved correctly and `apiBaseUrl` was baked in as the real configured URL.

---

## QA & stability pass: live re-verification

A later pass re-ran the full live verification against the running stack (`docker compose up -d`) after fixing the four issues found by that pass's independent audit (see [Security Decisions](../security/decisions.md)): signup, duplicate-signup handling, pre-verification login rejection, account verification (single-use, and its JWT expiry now correctly matches its Redis TTL/emailed wording), login, refresh rotation, reuse detection (confirmed the whole session family is revoked, not just the reused token), logout, `logout/all`, password-reset request+confirm, the new self-service current-password requirement (rejected without it, accepted with the correct one), PBAC allow/deny, policy CRUD (create/read/update/history/delete), the authorization audit log, rate limiting/account lockout (429 after repeated failures), and OAuth2 PKCE initiation (correct `code_challenge`/`state`/`oauth_state` cookie). Both production Docker images (`docker/backend.Dockerfile`, `docker/frontend.Dockerfile --target production`) built and the frontend image was confirmed to actually serve (`200` from its nginx container). `pip-audit` and `npm audit --audit-level=high` both reported zero known vulnerabilities.

---

## Sidebar ordering, multi-origin CORS, and the `/app/logs`/`.coverage` permission bugs

This round of changes (see the project story's Jul 27 entry) was verified against real container behavior far more directly than most: the sidebar `extraNavItems`/`order` prop was tested via `docker compose exec` running the actual frontend test suite inside the container; multi-origin CORS was confirmed live with `curl` requests carrying different `Origin` headers against a running backend, not just unit-tested; and the `/app/logs` and `.coverage` `PermissionError`s were root-caused by pulling real failed-run logs from GitHub Actions via `gh api`, not guessed at: see [Docker Overview: why `/app/logs` is a named volume](overview.md#why-applogs-is-a-named-volume-not-part-of-the-backendapp-bind-mount) and [running a one-off command inside a container](overview.md#running-a-one-off-command-inside-a-container) for the fixes those produced. `create_system_user.py`'s promotion/deletion paths were similarly verified against a real running Postgres: inserting a genuine Google-only row (`hashed_password IS NULL`), running the actual interactive script against it, and confirming the resulting row (and its policy assignments) directly via SQL rather than trusting the script's own printed output alone.
