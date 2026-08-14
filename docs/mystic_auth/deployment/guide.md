# Deployment Guide

Reference material shared across all three deployment modes. For
step-by-step instructions on running a given mode, see:

- [Dev Deployment](dev.md): local development, hot reload, no TLS
- [Local-Prod Deployment](local-prod.md): self-hosted production image shape,
  exposed via a free Cloudflare Tunnel, no public server needed
- [Prod Deployment](prod.md): your own server with Caddy-managed TLS

New to the repo? Start with [Dev Deployment](dev.md). It's the mode you'll
use day to day, and needs no domain, tunnel, or server.

## At a glance

| | Dev | Local-Prod | Prod |
|---|---|---|---|
| Compose file | `docker-compose.yml` | `docker-compose.local-prod.yml` | `docker-compose.prod.yml` |
| Frontend | Vite dev server (HMR) | nginx serving the static build | nginx serving the static build |
| Source code | Bind-mounted from host | Baked into the image | Baked into the image |
| Backend/worker reload | `--reload` on file change | Off | Off |
| Restart policy | None (manual) | `unless-stopped` | `unless-stopped` |
| Public entrypoint | None (`localhost` only) | Cloudflare Tunnel (`cloudflared`) | Caddy, automatic Let's Encrypt |
| TLS | None | Terminates at Cloudflare's edge | Caddy, on the host |
| Hosting model | Developer machine only | Your machine through Cloudflare Tunnel | Your own server with Caddy |
| Needs a public server? | No | No. Quick Tunnel needs no domain, Named Tunnel needs your own Cloudflare-managed domain | Yes, a server with public IP + DNS |
| Ports on host | frontend/backend/postgres/redis, all `localhost` | frontend (80) + backend (8000), for local debugging | only Caddy (80/443) |

See [Docker Overview: dev vs. production compose](../docker/overview.md#dev-vs-production-compose)
for the fuller service-by-service breakdown across all three Compose files.

---

## Choosing the right env template

The root `.env` file is the only file Docker Compose reads by default. Pick
one template for the mode you are running, copy it to `.env`, then edit that
copy. Do not combine values from multiple templates unless the deployment doc
for that mode explicitly says to.

| Mode | Copy this file | Use with | Best for |
|---|---|---|---|
| Dev | `.env.example` | `docker-compose.yml` | Local development with hot reload |
| Local-prod | `.env.local-prod.example` | `docker-compose.local-prod.yml` | Your machine through Cloudflare Tunnel |
| Prod | `.env.prod.example` | `docker-compose.prod.yml` | Your own server with Caddy TLS |

```bash
# Dev
cp .env.example .env
docker compose up

# Local-prod
cp .env.local-prod.example .env
docker compose -f docker-compose.local-prod.yml up -d --build

# Prod
cp .env.prod.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

Important rules:

- `.env` is user-managed local configuration. Keep it out of git.
- The example files are checked in documentation and defaults. Update them
  when the required settings change.
- `frontend/.env.example` is only for running the frontend directly with
  `npm run dev --prefix frontend`. Docker reads `VITE_*` values from the root
  `.env`.
- Production-style frontend values are baked into the image at build time:
  `VITE_API_BASE_URL`, `VITE_APP_NAME`, `VITE_SENTRY_DSN`, and
  `VITE_SENTRY_ENVIRONMENT`. After changing any of them, rebuild the frontend
  image with `--build`.
- Runtime backend values, such as `DATABASE_URL`, `SECRET_KEY`,
  `GOOGLE_REDIRECT_URI`, SMTP settings, and rate-limit settings, are read when
  containers start. After changing them, recreate or restart the affected
  containers.

---

## Single-origin frontend/backend routing

The frontend container's nginx (`docker/nginx.frontend.conf`) also proxies API
route prefixes to the backend. It forwards `/auth`, `/audit`, `/users`,
`/authorization`, and `/health` to the `backend` service. In both
production-style Compose files, the frontend container is pinned to
`172.28.0.10` so the backend can list that address in `TRUSTED_PROXY_IPS` and
trust its `X-Forwarded-For` header.

This single-origin setup works when `VITE_API_BASE_URL` is empty and
`TRUSTED_PROXY_IPS=172.28.0.10`. Both are set by default in
`.env.local-prod.example` and `.env.prod.example`. If your TLS terminator
sits in front of this nginx, forward to port 80 and let
nginx proxy the API paths internally. `proxy_add_x_forwarded_for` appends rather
than overwrites, so the client IP chain is preserved.

If you deploy the frontend elsewhere, point `VITE_API_BASE_URL` at the backend's
real public origin. Set `TRUSTED_PROXY_IPS` to the proxy that actually sits in
front of the backend for that topology.

---

## Required production environment variables

`.env.local-prod.example` and `.env.prod.example` already set the values
below correctly. This section explains the values you must review before
real production use:

- `ENVIRONMENT=production` disables `/docs`, `/redoc`, and `/openapi.json` on
  the backend. See `backend/app/main.py`.
- Generate or rotate `SECRET_KEY`, `GOOGLE_CLIENT_SECRET`,
  `GMAIL_APP_PASSWORD`, and `POSTGRES_PASSWORD` for production. Do not reuse
  local `.env` or CI values.
- Configure at least one user verification path before expecting normal users
  to reach the dashboard. Password signup requires SMTP email delivery because
  password accounts cannot log in until verified. Google login requires
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`, and
  creates a verified account using Google's verified-email signal.
- The CLI-created system superuser is the exception. It is marked verified by
  the script and can sign in with its password without Google or SMTP.
- Point `FRONTEND_BASE_URL` and `BACKEND_BASE_URL` at the real production
  hostnames. CORS in `backend/app/main.py` allows `FRONTEND_BASE_URL` plus
  comma-separated `FRONTEND_ADDITIONAL_BASE_URLS`. Leave the additional list
  unset for a single-origin deployment.
- Set `TRUSTED_PROXY_IPS` to your reverse proxy's address when a proxy sits in
  front of the backend. This lets rate limiting, lockout, and audit logging read
  the real client IP from `X-Forwarded-For`. Leave it unset for direct backend
  traffic. See [Security Hardening](../security/hardening.md#rate-limiting) and
  [Authorization Context Builder](../authorization/architecture.md#authorization-context-builder).
- `DEFAULT_APP_POLICIES` auto-assigns your own app's policies to every user
  once verified, alongside `self_service`. Leave it unset if your app has no
  default permissions beyond `self_service`. See [Writing and Testing
  Policies](../authorization/writing-testing-policies.md#giving-every-user-a-second-default-policy).
- `SENTRY_DSN` and `VITE_SENTRY_DSN` are optional. Leave them unset to disable
  error monitoring. If you enable self-hosted Bugsink in production, set real
  values for `BUGSINK_SECRET_KEY`, `BUGSINK_SUPERUSER_EMAIL`,
  `BUGSINK_SUPERUSER_PASSWORD`, and `BUGSINK_BASE_URL`.
- `SENTRY_DSN` and `VITE_SENTRY_DSN` differ in self-hosted Bugsink setups.
  `SENTRY_DSN` is backend-only and can use `bugsink:8000`. `bugsink-seed`
  auto-wires it through the shared volume. `VITE_SENTRY_DSN` is baked into the
  browser bundle at build time and must use the public route to Bugsink. See
  [Error Monitoring](../error-monitoring/overview.md).
- `VITE_API_BASE_URL`, `VITE_APP_NAME`, `VITE_SENTRY_DSN`, and
  `VITE_SENTRY_ENVIRONMENT` are consumed at **image build time**, not container
  runtime. `docker-compose.local-prod.yml` and `docker-compose.prod.yml` pass them to
  `docker/frontend.Dockerfile` as build args. Set them in the root `.env` before
  `docker compose -f docker-compose.local-prod.yml up -d --build` or
  `docker compose -f docker-compose.prod.yml up -d --build`. Values only in
  `frontend/.env` are invisible to Compose interpolation.

---

## Database migrations

The `alembic` service runs `alembic upgrade head` once and exits. `backend`,
`taskiq_worker`, and `taskiq_scheduler` all wait on it using Compose's `service_completed_successfully`
condition, so nothing serves traffic against an unmigrated schema.

Before applying a migration in production, review the generated script under
`backend/alembic/versions/`, especially anything that drops or alters a column
or table. Alembic autogenerate is a starting point, not a safety guarantee.

---

## Backups

`scripts/db/db_backup.sh` and `scripts/db/db_restore.sh` wrap the `pg_dump` and `psql`
commands below. They read `POSTGRES_USER` and `POSTGRES_DB` from `.env`, run
through Docker Compose, and make no cloud or provider assumptions.

```bash
# Dump the running postgres service to backups/<db>-<timestamp>.sql
scripts/db/db_backup.sh
# Against the production compose file instead of the dev one:
scripts/db/db_backup.sh docker-compose.local-prod.yml

# Restore a dump. Use -y to skip confirmation.
scripts/db/db_restore.sh backups/mystic_auth-20260717-120000.sql
```

These scripts are the "how", not the "when". There is no scheduler in this repo
because no specific production host is assumed. Wire `scripts/db/db_backup.sh` into
whatever your host provides, such as cron, a systemd timer, managed Postgres
backups, or a sidecar container. Choose a schedule that matches your data's
change rate. Daily is a reasonable default for most small apps. Store dumps
somewhere durable off the host, and periodically test a restore.

Equivalent raw commands, if you'd rather not use the scripts:

```bash
docker compose exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup-$(date +%F).sql
docker compose exec -T postgres psql -U $POSTGRES_USER $POSTGRES_DB < backup-2026-07-13.sql
```

---

## Graceful shutdown

`backend/app/main.py` registers a FastAPI `lifespan` handler that runs on
shutdown, including `docker stop` and rolling restarts under an orchestrator. It
disposes the SQLAlchemy connection pool and closes the Redis client cleanly.

---

## Production host requirements

This template assumes a Docker-capable host that can run long-lived services.
Use `docker-compose.prod.yml` when this stack should own the public HTTP/HTTPS
entrypoint through Caddy. Use `docker-compose.local-prod.yml` when another
reverse proxy or TLS terminator sits in front of the stack.

At minimum, a production deployment needs:

- A host that can run Docker Compose continuously.
- Persistent storage for Postgres, Caddy certificates, and Bugsink state.
- Network access for SMTP email delivery.
- DNS pointing at the public host before starting `docker-compose.prod.yml`.
- A backup schedule for Postgres dumps or volume snapshots.
- Monitoring and alerting appropriate for the environment.

The backend, frontend nginx, Postgres, Redis, Taskiq worker, Taskiq scheduler,
Alembic migration runner, and Bugsink services are all included in the Compose
files. The email pipeline depends on the long-running `taskiq_worker` and
`taskiq_scheduler` services connected to Redis.
request-driven serverless backend deployments are intentionally out of scope.

---

## Limitations of this deployment approach

- No infrastructure as code is provided. The steps above are manual host setup
  and Docker Compose operations.
- No automated backups are wired up. See
  [Concerns: database backups](../concerns/README.md#database-backups-are-scripted-but-not-scheduled).
  Error monitoring and alerting are available but opt-in. See
  [Error Monitoring](../error-monitoring/overview.md).
- Capacity planning, host hardening, backups, and alerting remain deployment
  responsibilities outside this template.
