# Security Decisions: Infrastructure
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Authentication Glossary](../glossary/authentication.md).*

See [Security Decisions](decisions.md) for the full index, including auth/session and product
decisions. This page covers the *why* behind infrastructure choices: image builds, settings
parsing, error monitoring, and the background task queue.

---

## `.dockerignore` previously let local files leak into built images

Two real, verified bugs found during a pre-release image-contents audit, both about files that exist on a developer's machine ending up baked into a Docker image that gets built and potentially shipped from that machine. Neither is something a template *consumer* needs to act on, since the fix is already in `.dockerignore`.

1. **Local access logs (`backend/logs/`) were baked into the backend image.**
   - `backend/mystic_auth/logging/logging_config.py` creates this directory on import and writes real request data to it (paths, timestamps, correlation IDs) via a `TimedRotatingFileHandler`.
   - `.dockerignore` had `*.log`, which only matches paths ending in exactly `.log`: the rotated sibling files that handler creates (`access.log.2026-07-19`, not `access.log.log`) don't match, and `backend.Dockerfile`'s `COPY backend/ .` copied them straight in.
   - Verified concretely: a throwaway container built from the image (no bind mount) had 23MB of real local `backend/logs/*` content sitting in it.
   - This isn't just wasted space: it's a snapshot of whoever's local dev traffic happened to be in that directory at build time, shipped inside a distributable artifact, and it made every image build non-reproducible (content depended on the builder's own local log history).
   - Fixed by adding `backend/logs/` explicitly.

2. **`__pycache__/` and related patterns weren't actually excluding nested directories.**
   - `.dockerignore` had bare `__pycache__/`, `*.pyc`, `*.pytest_cache/`, which look like they should match at any depth, but empirically didn't: a built image still contained `__pycache__/` directories nested under `backend/app/**/` and `backend/mystic_auth/**/` (bytecode caches that accumulate on the *host* filesystem because `docker-compose.dev.yml`'s dev backend service bind-mounts `./backend:/app`, so Python running inside that container writes `.pyc` files straight back to the host, not into an isolated container layer).
   - Verified by building the image both before and after the fix and listing its actual contents each time.
   - Fixed by using explicit `**/`-prefixed recursive patterns (`**/__pycache__/`, `**/*.pyc`, `**/.pytest_cache/`) instead of relying on bare patterns to recurse on their own.

3. **Not affected**: the production-target frontend image (`docker/mystic_auth/dockerfiles/frontend.Dockerfile`'s `production` target), verified separately, since it only ever copies `--from=builder /app/dist` (the compiled static bundle) into the final `nginx` stage, never the intermediate `builder`/`dev` stages' full source tree where a stray `frontend/coverage/` (also newly excluded, though harmless content, not a leak) would have mattered.

CI now has a regression guard for the `backend/logs/` case specifically; see [CI/CD Overview](../cicd/overview.md). See `.dockerignore` for the full current exclusion list.

---

## `Settings` ignores env vars it doesn't declare, because `.env` is shared with Docker Compose

1. `backend/mystic_auth/core/settings.py`'s `Settings.Config` sets `extra = "ignore"`, overriding pydantic-settings' own default of `extra = "forbid"`.
2. **Reason**: `env/mystic_auth/.env.dev` isn't exclusively this app's config file. Compose `env_file:` directives also hand the whole file to infra-only services that have no corresponding `Settings` field (`VALKEY_PASSWORD` for `valkey-server --requirepass`; `BUGSINK_*` for the optional self-hosted error-monitoring service, see [Error Monitoring](../error-monitoring/overview.md)).
3. **Why this was a confusing bug to track down**: with the default `"forbid"`, any such var crashed `Settings()` construction outright, but only sometimes.
   - `Settings.env_file = "env/mystic_auth/.env.dev"` is a *relative* path, so it only resolves to a real file (triggering pydantic-settings' own direct file parse, which builds a dict of literally every key in the file, not just ones it recognizes) when the process's working directory is the repo root.
   - The running app (`WORKDIR /app` in the Docker image) never hits this, since a relative `env/mystic_auth/.env.dev` there resolves to nothing and pydantic-settings falls back to reading only its declared fields from `os.environ`.
   - Running the test suite with `-w /repo` (required so tests can import `backend.app...`/`backend.mystic_auth...`, per [Testing Overview](../testing/overview.md)) does hit it, since `/repo/env/mystic_auth/.env.dev` genuinely exists there: so the exact same `env/mystic_auth/.env.dev` silently worked for the running app while crashing every test collection.
   - `extra = "ignore"` makes both paths behave identically instead. See `tests/backend/mystic_auth/unit/core/test_settings_unit.py`.

**Known trade-off, accepted deliberately**:

1. `"ignore"` also means a genuine typo in a variable this app *does* care about (`SENTRY_DSNN` instead of `SENTRY_DSN`, say) is silently dropped rather than raising a loud, easy-to-spot error: you'd only notice because the feature it configures quietly stays off, not because `Settings()` complained.
2. `SECRET_KEY` and every other field this app treats as load-bearing are still fully validated on their own terms regardless (see `_secret_key_minimum_strength` below, and each field's required-vs-defaulted status in `Settings` itself): `extra = "ignore"` only affects keys the model was never going to look at anyway.
3. Given `env/mystic_auth/.env.dev.example` documents every real field inline, this was judged the better trade against a shared `env/mystic_auth/.env.dev` file crashing the app outright over a var another service in the same compose stack legitimately needs.

---

## A malformed `SENTRY_DSN` must never crash the app

1. `error_monitoring/sentry_service.py::init_sentry()` runs unguarded at import time in `main.py`, before the app's own `global_exception_handler` exists to catch anything: it has to protect itself.
2. `sentry_sdk.init()` raises (`sentry_sdk.utils.BadDsn`) on a malformed DSN string, verified directly: `sentry_sdk.init(dsn="not-a-valid-dsn-at-all", ...)` throws rather than degrading gracefully.
3. Since `SENTRY_DSN` is meant to be a purely optional, best-effort setting (see [Error Monitoring](../error-monitoring/overview.md)), a typo in it must not be able to take down authentication for every user. `init_sentry()` now wraps the `sentry_sdk.init()` call in a broad `try/except`, logs a clear warning (via `get_startup_logger()`, so it's visible directly in `docker compose logs` rather than buried in the routine-INFO-is-file-only log: see [Backend Architecture: logging](../architecture/backend.md#logging)), and returns with monitoring left off. The app itself starts regardless. See `tests/backend/mystic_auth/unit/error_monitoring/test_sentry_service_unit.py` (`test_init_sentry_does_not_raise_when_the_dsn_is_malformed`, `test_init_sentry_logs_a_warning_when_the_dsn_is_malformed`).
4. Also verified, separately: `capture_exception()` itself (called from the global exception handler on every request) is safe to call even when no Sentry client was ever successfully bound. `sentry_sdk`'s own public API is designed to never raise, by the SDK's own design principle that error-reporting code must never become a *worse* failure than the error it was reporting. Confirmed directly rather than assumed: calling `capture_exception()` with no `init_sentry()` ever having run produces no exception.

**A related, separately-found bug in the same area**: `JWTService.create_verification_token` previously hardcoded the JWT's own `exp` claim to `ACCESS_TOKEN_EXPIRE_MINUTES` (15min default) regardless of what its caller requested, while `account_verification_service.py` set the paired Valkey single-use key's TTL (and the verification email's own wording) to `RESET_TOKEN_EXPIRE_MINUTES` (60min default).

1. A user clicking the link between 15 and 60 minutes in got a confusing invalid/expired error despite the email and the Valkey key both saying it should still work.
2. Fixed by threading `expires_minutes` through from the caller.
3. Password-reset tokens (`password_service.create_reset_token`) were never affected: they build their own JWT directly with the caller's `expires_minutes`, a separate code path.

See `tests/backend/mystic_auth/unit/auth/token_logic/test_jwt_service_unit.py` (`test_create_verification_token_honors_explicit_expires_minutes`) and `tests/backend/mystic_auth/unit/auth/verify_account/test_account_verification_service_unit.py` (`test_create_verification_token_forwards_expires_minutes_to_jwt_service`).

---

## Background task queue: Taskiq vs Celery

The app is fully async (FastAPI, SQLAlchemy async, `asyncio` throughout), and [Taskiq](https://taskiq-python.github.io/) was chosen over [Celery](https://docs.celeryq.dev/) for the one background job this template had at the time (sending email). **Superseded**: Taskiq was later replaced with Procrastinate; see [Taskiq replaced with Procrastinate](#taskiq-replaced-with-procrastinate) below and [Background Email Delivery](../background-workers/procrastinate.md). Kept here as historical record of the original Taskiq-vs-Celery reasoning, which is unaffected by that later swap: the argument below is about async-native task execution in general, not specific to which async-native queue eventually won.

**Why an async application changes the calculus at all**:

1. Celery's worker model predates `asyncio` and is fundamentally synchronous/thread-or-process-based.
2. Running truly async task code under Celery means either wrapping every async call in `asyncio.run(...)` per task (defeats the point: you get a new event loop per task, no shared connection pooling across tasks in a worker process) or reaching for `gevent`/`eventlet` monkey-patching to fake concurrency, which has its own long history of subtle incompatibilities with async libraries (`asyncpg`, `valkey.asyncio`, `aiosmtplib`: all already in use here) that patch at the socket/greenlet level instead of participating in the same event loop.
3. Taskiq's broker/worker are `async def` from the ground up, so `send_email_task` is a plain coroutine that shares the same `asyncio` primitives (and, in principle, the same connection pools) as the rest of the app: no bridging layer.

**Celery's real strengths, stated fairly**: this is not a "Celery is bad" argument:
1. **Maturity and ecosystem**: over a decade of production use, extensive documentation, first-class support in most PaaS/deployment guides, mature monitoring (Flower), broker flexibility (RabbitMQ, SQS, Valkey, and more), and a huge base of Stack Overflow/blog troubleshooting content that a niche library like Taskiq simply doesn't have yet.
2. **Feature depth**: complex workflows (chains, chords, groups), rate limiting per task, more granular retry/backoff policies out of the box, and a battle-tested scheduler (`celery beat`).
3. For a team already running a synchronous (WSGI) stack, or with existing Celery operational expertise, Celery remains the safer default: there's no async-compatibility problem to solve if nothing else in the stack is async either.

**Why this project chose Taskiq anyway**:

1. The whole backend is already async end-to-end, and Valkey is already a hard dependency for rate-limiting and login-lockout state, so a Valkey-backed Taskiq broker (`ValkeyStreamBroker`) adds zero new infrastructure.
2. Celery would either need its own broker (typically RabbitMQ, adding a service) or reuse Valkey in a less idiomatic way (Celery-over-Valkey is supported but is the less-travelled path in Celery's own ecosystem, with known limitations around visibility/ack timeouts).
3. Given the task volume here is one job (email sending), Taskiq's smaller feature set is not a real cost: the deciding factor was avoiding a sync/async impedance mismatch and avoiding a second piece of broker infrastructure, not a claim that Taskiq is categorically better.

---

## Taskiq replaced with Procrastinate

Taskiq (see above) was later replaced in full with [Procrastinate](https://procrastinate.readthedocs.io/) (Postgres-native, no Valkey broker): not a gradual migration, a full swap. See [Background Email Delivery](../background-workers/procrastinate.md) for the resulting architecture.

**Why**: two items that sat in [Concerns](../concerns/README.md) as accepted, unresolved gaps under Taskiq's design turned out to be architectural consequences of the Valkey-broker choice itself, not things that needed a workaround:

- **No dead-letter queue or alerting for permanently-failed emails.** Under Taskiq, a permanently-failed job (all retries exhausted) was simply dropped after its final traceback was logged: nothing stored it anywhere queryable. Procrastinate's jobs are rows in `procrastinate_jobs` from the moment they're deferred; a permanently-failed job's row just sits at `status='failed'`, directly queryable via plain SQL, by construction rather than by adding a table to write failures into.
- **`taskiq_scheduler` was a single point of failure for retry delivery.** Taskiq's `SmartRetryMiddleware` only computes a retry's due-time; something else has to poll that store and re-enqueue due retries, which is why a separate `taskiq_scheduler` container existed at all: if it was down, a scheduled retry silently never fired. Procrastinate writes a retry's `scheduled_at` directly onto the same job row, and the worker's own fetch query picks it up once due, in the same process that runs everything else, including periodic/cron tasks (`@app.periodic`, via an internal `PeriodicDeferrer`). There's no second process to poll anything, so there's nothing for that process's downtime to silently break.

**Why not just add a dead-letter table and a second scheduler replica to Taskiq instead**:

1. Both of Concerns' listed "possible fixes" would have worked, but each adds bespoke infrastructure (a hand-rolled failure table, a second scheduler instance plus whatever makes its polling safely idempotent) to work around gaps that don't exist in a design where the job queue's system of record is the same durable, already-present Postgres database the rest of the app already trusts, instead of an ephemeral Valkey stream.
2. Since this template's only other reason for a Taskiq-style async-native broker (see the Taskiq-vs-Celery reasoning above) was avoiding a sync/async impedance mismatch, and Procrastinate is equally `async def`-native, the swap keeps everything the original decision cared about while dropping Valkey as a broker entirely: Valkey remains in the stack for rate-limiting/lockout state and a non-authoritative token-version cache (see [Concerns](../concerns/README.md)), just no longer for background jobs.

**What changed concretely**: `backend/mystic_auth/taskiq_tasks/` (broker, result backend, Valkey-backed schedule source, `ResilientValkeyStreamBroker`'s fresh-Valkey startup-race handling) is gone entirely, replaced by `backend/mystic_auth/procrastinate_tasks/` (`procrastinate_app.py`'s `App`/`PsycopgConnector`, `email_tasks.py`, `account_purge_tasks.py`). One new Alembic migration applies Procrastinate's own packaged schema SQL (read from the installed package, not hand-transcribed) rather than a separate `procrastinate schema --apply` step, keeping this template's Alembic-only schema-change discipline intact. The `taskiq_scheduler` container is gone; `taskiq_worker` became `procrastinate_worker`, running `procrastinate --app=...worker` (which also runs the periodic-task deferrer internally) with `procrastinate --app=... healthchecks` as its healthcheck instead of grepping `/proc` for a process name.

---

## Least-privilege app DB role instead of running as Postgres superuser

1. Every service previously connected to Postgres as the same `postgres` superuser (`DATABASE_URL`), including the request-serving backend and the Procrastinate worker's task bodies.
2. Migration `b1e6a9f3c7d2_add_least_privilege_app_role.py` adds a second role, `mystic_auth_app`, with only `SELECT`/`INSERT`/`UPDATE`/`DELETE` on application tables: no `CREATE`/`ALTER`/`DROP`/`TRUNCATE`, no `CREATEROLE`/`CREATEDB`, no superuser.
3. `database/connection.py` prefers the new `APP_DATABASE_URL` setting when it's set, falling back to `DATABASE_URL` otherwise, so this is opt-in and backward-compatible; `env/mystic_auth/.env.dev.example` ships it enabled by default for fresh setups.
4. Migrations (`alembic upgrade head`) still run as the `postgres` superuser, since DDL and role management require it. See [Database Design: Database roles](../database/design.md#database-roles) for the diagram and full mechanics.

**Why this is worth doing even though PBAC already governs access**:

1. PBAC decides what an *authenticated request* is allowed to do, entirely inside the Python application. It says nothing about what Postgres itself will permit a given *credential* to do, independent of the application layer: a compromised dependency reusing the app's live DB connection, a bad ad hoc script, or a leaked runtime credential all bypass PBAC by construction, since PBAC never runs outside `AuthorizationService.authorize()`.
2. Least-privilege role separation is standard production hygiene regardless of the app's own authorization model (every managed Postgres provider enforces it by default), and it's cheap: one role, a handful of `GRANT`s, no ongoing per-table maintenance.

**What this does and does not protect against, precisely**:

1. It does **not** protect the app's own data confidentiality or integrity from a leaked *runtime* credential: `mystic_auth_app` necessarily has full CRUD on application tables to function, so a leaked `APP_DATABASE_URL` can still read every row or overwrite them, exactly as a leaked superuser credential could. That risk needs secrets management and network-level restrictions (Postgres unreachable from outside the app's own private network), not a DB-role change, and is out of scope here.
2. What the role split *does* narrow, for that same leaked credential: it can no longer run schema-destroying DDL, create a new Postgres role (e.g. a persistence backdoor), or read another role's credentials (`pg_authid`), capability outside the app's own table data, not inside it.

**Why not Row-Level Security**: considered and deliberately not implemented.

1. RLS's actual purpose is filtering *which rows* a role sees within a shared table, which only matters when a table holds rows belonging to multiple untrusted parties connecting with different roles: the classic case is multi-tenant SaaS, or an architecture where Postgres itself is a direct trust boundary (e.g. Supabase, where RLS *is* the security boundary because PostgREST exposes the database straight to end-user clients).
2. This app is single-tenant (no `tenant_id`/`org_id` anywhere) and Postgres is never a direct trust boundary: every access is mediated by the FastAPI app, where PBAC already decides everything, including privileged operations.
3. Without a real per-row ownership column to filter on, an RLS policy here would degenerate into `USING (true)` for the app role: no different from the table grant this migration already does, but with an added footgun. Every *future* table added by a downstream fork must be remembered and explicitly `ENABLE ROW LEVEL SECURITY`'d, or it defaults to open to any role with a grant rather than protected, which is worse than not having RLS at all since it looks protected but isn't.
4. Revisit this if a downstream fork ever adds real multi-tenancy (a `tenant_id`/`org_id` column): at that point RLS becomes the standard, correct defense-in-depth layer underneath the app's own tenant checks.

---

## Test suite gets its own dedicated Postgres database

`tests/backend/conftest.py` now redirects `DATABASE_URL`/`APP_DATABASE_URL` to a `mystic_auth_test` database on the same Postgres server, instead of the real `mystic_auth` database a running dev stack's own `backend`/`procrastinate_worker` containers use. See [Testing Overview: Dedicated test database](../testing/overview.md#dedicated-test-database) for the mechanics.

**Why**: a real, reproducible incident, not a hypothetical.

1. A dev-stack `procrastinate_worker` container ran for 47 minutes logging 801 `ConnectorException` errors, then was killed.
2. **Root cause**: the historical `_procrastinate_app_lifecycle` fixture deleted every row from `procrastinate_jobs` after each test, while a worker was still processing jobs in the same database (same Postgres, whether reached via the internal `postgres` hostname from inside the Docker network or `localhost:5433` from the host). The fixture now deletes only terminal rows and leaves `todo`/`doing` jobs for the worker to finish.
3. A real worker picking up a test-deferred job (most commonly an audit-log write, since every protected route logs one) would sometimes lose the race: it finished processing successfully, but by the time it tried to persist `status='succeeded'` back onto that job's row, the test's own teardown had already deleted it out from under it. "Job was not found or not in doing/todo status" was logged, then repeated on the next job, and the next, until something (most likely WSL2's own memory manager, given `OOMKilled` was `false` in Docker's own accounting) killed the container.

**Why the dedicated database remains necessary even with the narrower cleanup**:

1. Scoping the teardown's `DELETE` to only completed jobs closes the known in-flight-job race, but the underlying problem, a test suite and a live, independently-running application sharing one database's tables, is a broader hazard than just this one symptom.
2. The same class of collision could show up anywhere else a test's cleanup fixture deletes by a query rather than by exact ownership (e.g. `_cleanup_users`, `_cleanup_audit_log`).
3. A dedicated database removes the shared tables entirely, which is the only fix that also protects against variants of this bug nobody has hit yet.

**Skipped in CI**: CI already provisions its own dedicated, single-purpose `mystic_auth_ci` Postgres service per run (see `.github/workflows/ci.yml`), with no dev-stack container ever running alongside it, so there's nothing there for this redirect to protect against - detected via the `CI` env var, set by GitHub Actions and effectively every other CI provider by convention.

---
