# Docker Overview

## Services

| Service | Image / build | Purpose |
|---|---|---|
| `postgres` | `postgres:15` | Primary database |
| `redis` | `redis:7` | Cache, rate limits, lockout counters, refresh-token jti registry, single-use tokens, taskiq broker |
| `backend` | `docker/backend.Dockerfile` | FastAPI app (uvicorn) |
| `frontend` | `docker/frontend.Dockerfile` (`dev` target locally, `production` target in prod) | React SPA: Vite dev server locally, nginx-served static build in prod |
| `taskiq_worker` | `docker/backend.Dockerfile` (same image as `backend`, different `command:`) | Consumes the email-sending task queue: see [Background Workers](../background-workers/taskiq.md) |
| `alembic` | `docker/backend.Dockerfile` (same image, one-shot) | Runs `alembic upgrade head` then exits; `backend`/`taskiq_worker` wait on its success in prod |
| `bugsink` | `bugsink/bugsink:2` (pulled, not built) | Self-hosted error monitoring, starts by default with the stack. See [Error Monitoring](../error-monitoring/overview.md) |
| `bugsink-seed` | `bugsink/bugsink:2` (same image, one-shot) | Runs once `bugsink` is healthy: creates its "MysticAuth" team/project (idempotent) and writes the seeded DSN(s) into the `bugsink_dsn` volume. Locally, writes both the backend and frontend DSN forms, and both `backend`/`frontend` read from the volume at their own startup. In prod, writes only the backend form and only `backend` reads it: `frontend`'s `VITE_SENTRY_DSN` is baked in at image build time instead, so there's nothing for it to wait on at container startup (see [Error Monitoring](../error-monitoring/overview.md)) |

`backend`, `taskiq_worker`, and `alembic` all build from the **same** `docker/backend.Dockerfile` image with different `command:` overrides: keeps dependency versions and application code identical across all three roles by construction.

The `postgres` service also mounts `docker/postgres-init/` to `/docker-entrypoint-initdb.d/`: on a fresh volume only, it creates the separate `bugsink` database the service above uses, so it doesn't require a second Postgres container.

### Startup order

```mermaid
flowchart LR
    subgraph Data["Data layer"]
        postgres(("postgres"))
        redis(("redis"))
    end

    subgraph App["Application services"]
        alembic["alembic<br/><small>runs once, exits</small>"]
        backend["backend"]
        taskiq["taskiq_worker"]
        frontend["frontend"]
    end

    subgraph Monitoring["Error monitoring"]
        bugsink["bugsink"]
        bugsinkseed["bugsink-seed<br/><small>runs once, exits</small>"]
    end

    postgres --> alembic
    redis --> alembic
    alembic -->|"prod: waits for<br/>success. dev: no gate"| backend
    alembic --> taskiq
    postgres --> backend
    redis --> backend
    postgres --> taskiq
    redis --> taskiq
    backend -->|healthy| frontend
    postgres --> bugsink
    bugsink -->|healthy| bugsinkseed
```

## Dockerfiles

- **`docker/backend.Dockerfile`**: two-stage build: a `builder` stage compiles native dependencies (`gcc`, `libpq-dev`) into an isolated venv; the runtime stage is `python:3.11-slim` with only `libpq5` (runtime client lib, not the dev headers), running as a non-root `app` user. Ships a `HEALTHCHECK` against `/health/ready` as a fallback for when the image runs outside Compose (Compose's own healthcheck, defined per-service, is what actually gates dependent-service startup).
- **`docker/frontend.Dockerfile`**: three stages: `dev` (default target: `node:20.20.2-bullseye`, Vite dev server with HMR, port 5173, runs as root since the container needs to `npm install` against the bind-mounted `frontend/` and root avoids host/container UID mismatches on the bind mount: the `production` stage below is the one that runs as a non-root user), `builder` (compiles the production bundle; takes `VITE_API_BASE_URL`/`VITE_APP_NAME`/`VITE_SENTRY_DSN`/`VITE_SENTRY_ENVIRONMENT` as build args, since this stage has no bind-mounted `frontend/.env` to read them from the way `dev` does: wired from the root `.env` via `docker-compose.prod.yml`'s `build.args`, see [Deployment Guide](../deployment/guide.md#required-production-environment-variables)), `production` (`nginx:1.27-alpine` serving the static build as a non-root `nginx` user, port 80, `HEALTHCHECK` via `wget`).
- **`docker/nginx.frontend.conf`**: SPA fallback to `index.html`, gzip, security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP). No HSTS at this layer: by design, since TLS terminates in front of this container in a real deployment, not here (see [Security Hardening](../security/hardening.md#security-response-headers)).
- **`.dockerignore`** (repo root: the build context for both Dockerfiles above is `.`, not `backend/`/`frontend/` individually, so its patterns are written relative to the repo root): excludes `backend/logs/` (real local request logs, previously leaking into the backend image: a real bug, not a hypothetical one, see [Security Decisions](../security/decisions.md#dockerignore-previously-let-local-files-leak-into-built-images)) and `**/`-recursive patterns for `__pycache__/`/`*.pyc`/`.pytest_cache/` (bare patterns without the `**/` prefix looked like they should already match at any depth but empirically didn't).

### Why `frontend` sets `pull_policy: build`

`frontend` is the only service in either compose file with both `image:`
(`mystic-auth-frontend:dev`/`:prod`) and `build:` set. Every other service
either only has `build:` (nothing to pull) or only has `image:` (postgres,
redis, bugsink, genuinely pulled from a registry). Without `pull_policy:
build`, Compose attempts a pull of `image:` first on every run, which
always fails (`pull access denied for mystic-auth-frontend, repository
does not exist`) since this tag is never published, before falling back to
building anyway. Harmless but noisy on every startup; `pull_policy: build`
skips straight to building.

## Dev vs. production compose

| | `docker-compose.yml` (dev) | `docker-compose.prod.yml` |
|---|---|---|
| Frontend | Vite dev server, HMR, bind-mounted source | nginx serving the baked-in static build |
| Backend/worker | `--reload`, bind-mounted `./backend:/app` | No reload, code baked into the image |
| Restart policy | `restart: always` (postgres/redis only; backend/frontend/worker have none) | `unless-stopped` on every long-running service |
| Ports exposed | 5433 (postgres), 6380 (redis), 8000 (backend), 5173 (frontend) all published to host: non-default DB/cache host ports deliberately chosen to dodge the common local 5432/6379 collision; containers still reach each other at `postgres:5432`/`redis:6379` over the Docker network regardless | Only 8000 (backend) and 80 (frontend) published |
| `backend`/`taskiq_worker` startup gate | `postgres`/`redis` healthy | `postgres`/`redis` healthy **and** `alembic: service_completed_successfully` |

Both compose files assume a reverse proxy / TLS terminator sits in front of the stack in a real deployment: neither attempts to provision TLS itself. See [Deployment Guide](../deployment/guide.md).

### Running a one-off command inside a container

`docker compose exec -w /repo backend <command>` (used throughout this documentation to run tests against the whole repo: see [Testing Overview](../testing/overview.md)) runs `<command>` with its working directory set to `/repo` inside the container (the whole-repo bind mount: see `docker-compose.yml`'s `backend` service).

**On Windows, using Git Bash specifically:** this can fail with `OCI runtime exec failed: exec failed: Cwd must be an absolute path`, even though `/repo` clearly is one. Git Bash silently rewrites arguments that look like Unix paths into Windows paths before handing them to non-MSYS programs like `docker.exe`, which mangles `-w /repo` into something Docker no longer recognizes. Two ways around it, either works:

```bash
# Option 1: disable Git Bash's path rewriting for this one command
MSYS_NO_PATHCONV=1 docker compose exec -w /repo backend <command>

# Option 2: cd inside the container's own shell instead of using -w
docker compose exec backend bash -c "cd /repo && <command>"
```

This is specific to Git Bash's own path handling: PowerShell, Command Prompt, and native Linux/macOS terminals all run `-w /repo` as written, with nothing to work around.

**Running `pytest` specifically needs `--user root`, on native Linux.** `pytest.ini` writes coverage output (`.coverage`, `htmlcov/`) to the current working directory: `/repo`, the whole-repo bind mount: and that directory's actual ownership on disk is whatever owns the host's checkout, not the container's own non-root `app` user (same root cause as [why `/app/logs` is a named volume](#why-applogs-is-a-named-volume-not-part-of-the-backendapp-bind-mount), just for coverage's output files instead of the app's own log directory, and not something a single named-volume mount can carve out the way `/app/logs` could, since coverage's output isn't confined to one fixed path). Invisible on Docker Desktop for the same reason as always; a hard `PermissionError`/`INTERNALERROR` on native Linux otherwise:

```text
docker compose exec --user root -w /repo backend pytest tests/backend/
```

Running as root here is scoped to this one throwaway test invocation: it has no bearing on the actual application, which still runs as its normal non-root `app` user by default (`backend.Dockerfile`'s `USER app`) for every real request it serves. One minor side effect worth knowing on native Linux specifically: `.coverage`/`htmlcov/` end up root-owned on the host afterward, so a later `rm -rf htmlcov/` may need `sudo`. Docker Desktop (Windows/Mac) doesn't have this wrinkle either, for the same permissive-bind-mount reason as above.

## Healthchecks

| Service | Check | Notes |
|---|---|---|
| `postgres` | `pg_isready` | |
| `redis` | `redis-cli ping` | |
| `backend` | `GET /health/ready` via a Python one-liner (no curl in the slim image) | Confirms DB + Redis connectivity, not just process liveness. Budget is 10 retries / 30s start period (~130s total) rather than a tighter 5/10s (~60s): generous headroom for a genuinely cold first boot on modest or shared hardware. This is a secondary hardening, not the fix for the specific bug below: no healthcheck budget helps if the container is actually crash-looping. |
| `frontend` (prod) | `wget` against `/` | |
| `frontend` (dev) | none | Acceptable for local dev: Vite's own dev server failure is immediately visible in the terminal |
| `taskiq_worker` | greps `/proc/*/cmdline` for `taskiq` | Overrides the inherited HTTP healthcheck from `backend.Dockerfile`, since the worker serves no HTTP and would otherwise always report unhealthy |
| `bugsink` | `GET /health/ready` via a Python one-liner | Same reasoning as `backend`'s own check |
| `alembic` | none | One-shot; `service_completed_successfully` is the signal other services wait on, not a healthcheck |
| `bugsink-seed` | none | One-shot, same shape as `alembic`: creates the Bugsink project/DSN once, then exits 0 |

### Day-to-day: dev-up helpers

`docker compose up` (no `-d`) attaches to and interleaves *every* service's
full stdout/stderr into one stream: Postgres's own boot log, Alembic's
migration list, Bugsink's 100+ Django migrations, and (worst of it)
Bugsink's own healthcheck hitting `/health/ready` every 10 seconds,
forever, all mixed in with whatever you actually started the stack to look
at. None of that is useful once the stack is actually up.

Use the helper for your shell:

```bash
# Git Bash, WSL, Linux, macOS
./scripts/dev-up.sh
```

```powershell
# PowerShell
.\scripts\dev-up.ps1
```

```bat
rem Command Prompt
scripts\dev-up.cmd
```

The helper script starts the stack detached, explicitly restarts `backend`
and `taskiq_worker` (so their own boot banner : Uvicorn's startup lines,
Taskiq's "Listening started" : is always fresh and worth tailing, even on a
rerun against a stack that was already up and Compose left both containers
alone), waits for every long-running service to report healthy (or just
running, for `frontend` dev, which has no healthcheck: see the table
above), prints one `docker compose ps`-style status line per service, then
tails fresh logs from `backend`/`frontend`/`taskiq_worker`: their startup
banners, API traffic, frontend dev-server activity, and async email-task
execution. It records a timestamp before starting Compose and passes that
to `docker compose logs --since`, so old request/task activity from a
previous, unrelated run doesn't get replayed as if it belonged to the
current startup. If a service fails to come up, the status table still
prints (so you can see exactly which one), and the script exits non-zero
instead of silently tailing a broken stack.

Because `backend`/`taskiq_worker` restart on every invocation, running the
helper a second time while it (or another copy of it) is already tailing
the same stack will restart both again out from under the first run : each
invocation doesn't know about the other. Harmless (in-flight requests/tasks
just retry), but expect an extra boot banner in that case.

It deliberately does **not** use `docker compose up --wait`, despite that
being the obvious built-in choice: `--wait` treats *any* exited container
as a failure to reach "running," with no exception for a one-shot job that
exited 0 on purpose. `alembic` and `bugsink-seed` (see the table above)
are exactly that: `--wait` reports this stack as failed on every single
successful start, because those two containers correctly finished and
exited. The dev-up helpers poll the long-running services' own status
text directly instead, entirely sidestepping that mismatch.

Plain `docker compose up` still has its place: pass it directly when you
want everything's full logs in one interleaved stream, e.g. actually
debugging Postgres/Bugsink/Alembic startup itself rather than the app.

### Why `/app/logs` is a named volume, not part of the `./backend:/app` bind mount

Dev's `backend`/`taskiq_worker` services bind-mount `./backend:/app` for hot-reload. `mystic_auth/logging/logging_config.py` writes to `/app/logs`, which is therefore, by default, inside that bind mount: meaning its actual ownership on disk is whatever owns the host's checkout of `backend/`, not whatever the container's own non-root `app` user is.

That's invisible on Docker Desktop (Windows/Mac), which doesn't enforce host-container UID matching on bind mounts: but it's a hard failure on native Linux: a fresh clone has no `backend/logs/` at all (it's gitignored), the container's `app` user can't create one inside a directory it doesn't own, and `os.makedirs()` raises `PermissionError` at import time, before the app even starts serving. This is exactly what broke this repo's own CI the first time a job actually booted the dev compose stack on a real Linux runner (GitHub Actions) rather than testing natively or via a bind-mount-free `docker build`/`docker run`: every previous CI job had run one or the other, so this had been latent, unnoticed, since dev compose was first written.

Fixed two ways together: `docker/backend.Dockerfile` now creates `/app/logs` and `chown`s it to the `app` user at build time (baked into the image), and `docker-compose.yml` mounts a Docker-managed volume (`backend_logs:/app/logs`) at that one path on top of the broader bind mount, for both `backend` and `taskiq_worker`. Docker initializes a fresh named volume by copying whatever already exists at that path in the image: ownership included: so the directory the app actually writes to always has the right owner, regardless of what UID owns the host's checkout. The tradeoff: `backend/logs/access.log` is no longer directly readable from the host filesystem in dev: use `docker compose exec backend tail -f logs/access.log`, or `docker compose logs backend` for WARNING+ (already terminal-visible regardless: see [Backend Architecture: Logging](../architecture/backend.md#logging)).

## Validation history

Live-verification passes against the running stack: what was run, what it found, what got fixed: live in their own doc so this one stays reference-only: see [Docker Validation History](validation-history.md).
