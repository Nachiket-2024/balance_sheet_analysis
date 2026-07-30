# Deployment Guide

## Dev vs Production

| | `docker-compose.yml` | `docker-compose.prod.yml` |
|---|---|---|
| Frontend | Vite dev server (HMR) | nginx serving the static build |
| Source code | Bind-mounted from host | Baked into the image |
| Backend/worker reload | `--reload` on file change | Off |
| Restart policy | None (dev: you restart manually) | `unless-stopped` on long-running services |

Local development:

```bash
./scripts/dev-up.sh      # Git Bash, WSL, Linux, macOS
.\scripts\dev-up.ps1     # PowerShell
scripts\dev-up.cmd       # Command Prompt
```

(or plain `docker compose up` if you want every service's logs interleaved; see [Docker Overview](../docker/overview.md#day-to-day-dev-up-helpers))

Production:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` assumes a reverse proxy / TLS terminator (nginx, Caddy, Traefik, or a cloud load balancer) sits in front of it: it exposes plain HTTP on ports 80 (frontend) and 8000 (backend) and does not attempt to provision TLS itself. See [Docker Overview](../docker/overview.md).

**Testing `docker-compose.prod.yml` locally**: both compose files share the same root `.env`; there's no separate `.env.prod`. Its `FRONTEND_BASE_URL=http://localhost:5173` is the dev (Vite) port; prod serves on port 80 via nginx, so OAuth2/email redirect links (built from `FRONTEND_BASE_URL`) point at a dead port until you change it. Set `FRONTEND_BASE_URL=http://localhost` in `.env` before a local prod test, and set it back to `:5173` before returning to the dev-up helper. A real deployment doesn't hit this: there, `FRONTEND_BASE_URL` is your actual domain, set once.

## Required production environment variables

Same variables as `.env.example`, with these called out specifically for production:

- `ENVIRONMENT=production`: disables `/docs`, `/redoc`, and `/openapi.json` on the backend (see `backend/app/main.py`).
- `SECRET_KEY`, `GOOGLE_CLIENT_SECRET`, `GMAIL_APP_PASSWORD`, `POSTGRES_PASSWORD`: generate/rotate these for production; never reuse the values from local `.env` files or CI.
- `FRONTEND_BASE_URL` / `BACKEND_BASE_URL`: must point at the real production hostnames; CORS (`main.py`) allows this origin plus any comma-separated `FRONTEND_ADDITIONAL_BASE_URLS` (e.g. a second domain, or staging sharing this backend), and that should be left unset for the common single-origin case.
- `TRUSTED_PROXY_IPS`: set this to your reverse proxy's own address(es) if you deploy one in front of the backend, so per-IP rate limiting/lockout resolve the real client IP from `X-Forwarded-For` instead of collapsing onto the proxy's IP for every request. See [Security Hardening](../security/hardening.md#rate-limiting) and [Authorization Context Builder](../authorization/architecture.md#authorization-context-builder) (covers `auth/security/client_ip.py`'s IP resolution logic). Leave unset (default) for a direct deployment with no reverse proxy.
- `SENTRY_DSN` / `VITE_SENTRY_DSN`: optional, leave unset to keep error monitoring fully disabled. If enabling self-hosted Bugsink in production, `BUGSINK_SECRET_KEY`/`BUGSINK_SUPERUSER_EMAIL`/`BUGSINK_SUPERUSER_PASSWORD`/`BUGSINK_BASE_URL` also need real (non-`.env.example`-placeholder) values. **These two DSNs are not the same value in a self-hosted-Bugsink setup, and only one of them needs setting by hand**: `SENTRY_DSN` (backend, container-to-container) uses the Compose service address (`bugsink:8000`); `docker-compose.prod.yml`'s `bugsink-seed` service auto-wires this one for you, same as in dev, so leave it blank and let seeding fill it in. `VITE_SENTRY_DSN` (frontend, baked into the browser bundle at build time) is the one that genuinely needs a manual value: it needs whatever *publicly* reaches Bugsink in production, which, per its own no-exposed-port-by-default posture (see [Error Monitoring: security notes](../error-monitoring/overview.md#security-notes)), means a reverse-proxy route you set up deliberately, not `localhost`, and `bugsink-seed` has no way to know that address in advance. See [Error Monitoring](../error-monitoring/overview.md) for the full explanation, including the dev/prod split.
- `VITE_API_BASE_URL` / `VITE_APP_NAME` / `VITE_SENTRY_DSN` / `VITE_SENTRY_ENVIRONMENT`: unlike every other variable in this list, these are consumed at **image build time**, not container runtime: `docker-compose.prod.yml`'s `frontend` service passes them to `docker/frontend.Dockerfile` as build args, since the production nginx image has no bind-mounted `frontend/.env` for Vite to read the way the dev target does. They must be set in the root `.env` (not just `frontend/.env`) before `docker compose -f docker-compose.prod.yml up -d --build`, since `docker compose` only reads the compose file's own directory for `${VAR}` interpolation, so a value that only exists in `frontend/.env` is invisible to `docker-compose.prod.yml`. Point `VITE_API_BASE_URL` at the real public backend origin, not `localhost`, unless the frontend and backend share an origin behind the same reverse proxy.

## Database migrations

The `alembic` service runs `alembic upgrade head` once and exits; `backend` and `taskiq_worker` both wait on it (`depends_on: alembic: condition: service_completed_successfully` in `docker-compose.prod.yml`) so nothing serves traffic against a schema that hasn't been migrated yet.

Before applying a migration in production, review the generated migration script under `backend/alembic/versions/`: especially anything that drops or alters a column/table. Alembic's autogenerate is a starting point, not a guarantee of safety; a destructive migration should be reviewed like any other schema change before `alembic upgrade head` runs against production data.

## Backups

`scripts/db_backup.sh` and `scripts/db_restore.sh` wrap the `pg_dump`/`psql` commands below: environment-driven (read `POSTGRES_USER`/`POSTGRES_DB` from `.env`), Docker-only, no cloud/provider assumptions:

```bash
# Dump the running postgres service to backups/<db>-<timestamp>.sql
scripts/db_backup.sh
# Against the production compose file instead of the dev one:
scripts/db_backup.sh docker-compose.prod.yml

# Restore a dump (prompts for confirmation; -y skips the prompt)
scripts/db_restore.sh backups/mystic_auth-20260717-120000.sql
```

These scripts are the "how", not the "when": there's still no scheduler wired up in this repo, since no specific production host/cloud target is assumed (see [Concerns](../concerns/README.md)). Wire `scripts/db_backup.sh` into whatever your host provides (a `cron` entry, a systemd timer, a managed Postgres provider's built-in backups, or a sidecar container), on a schedule that matches your data's change rate (daily is a reasonable default for most small apps). Store the dumps somewhere durable off the host, and periodically test a restore: an untested backup is not a backup.

Equivalent raw commands, if you'd rather not use the scripts:

```bash
docker compose exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup-$(date +%F).sql
docker compose exec -T postgres psql -U $POSTGRES_USER $POSTGRES_DB < backup-2026-07-13.sql
```

## Graceful shutdown

`backend/app/main.py` registers a FastAPI `lifespan` handler that runs on shutdown (e.g. `docker stop`, or a rolling restart under an orchestrator): it disposes the SQLAlchemy connection pool and closes the Redis client cleanly instead of relying on the process dying and the OS reclaiming the sockets.

## Free / low-cost hosting options

This stack has four pieces that need hosting: backend (containerized FastAPI), frontend (static SPA build), Postgres, and Redis + a background worker process. The options below are a reasonable starting point for a template/side-project deployment: evaluate each provider's own limits (cold starts, storage caps, free-tier sleep policies) against what your actual deployment needs before relying on one.

### Backend (FastAPI, containerized)

- **Render** (free/hobby web service tier): deploys directly from `docker/backend.Dockerfile`; supports a separate "background worker" service type for `taskiq_worker` on the same repo. Free tier sleeps after inactivity (cold-start latency).
- **Fly.io**: deploys any Dockerfile; has a small free allowance. Good fit since the app is already fully containerized.
- **Railway**: Dockerfile-based deploys, usage-based free tier.

### Frontend (static SPA build)

- **Vercel** / **Netlify** / **Cloudflare Pages**: all have generous free tiers for a static build (`npm run build` → `frontend/dist/`); none need the `production` nginx image specifically, since they serve the static files themselves. If you do want the containerized nginx path (`docker/frontend.Dockerfile --target production`), use the same host as the backend instead.

### PostgreSQL

- **Neon**, **Supabase**, or **Railway**: all offer a free managed Postgres tier reachable over the internet; set `DATABASE_URL` to the provided connection string (must use the `postgresql+asyncpg://` scheme this app's async engine expects, not `postgresql://`).

### Redis

- **Upstash**: serverless Redis with a free tier, reachable over TLS from any host; set `REDIS_URL` accordingly. Note Upstash's free tier has request-count limits that matter here since Redis is used for rate limiting, lockout, and the taskiq broker (all high-frequency).

### Background worker (taskiq)

Needs a long-running process, not a request-driven serverless function: Render's/Railway's "background worker" service type (pointed at the same image, `command: taskiq worker mystic_auth.taskiq_tasks.email_tasks:broker`) is the most direct fit among the free-tier options above.

### Practical combination for a $0 deployment

Backend + worker on Render (two services from the same repo/image), frontend on Vercel/Netlify, Postgres on Neon, Redis on Upstash. Set `TRUSTED_PROXY_IPS` appropriately if the chosen backend host places its own reverse proxy in front of your container (most of the above do): otherwise per-IP rate limiting will silently collapse onto that proxy's IP for every request.

## Limitations of this deployment approach

- No infrastructure-as-code (Terraform/Pulumi/etc.) is provided: the steps above are manual, per-provider console/CLI actions.
- No automated backups are wired up: see [Concerns: database backups](../concerns/README.md#database-backups-are-scripted-but-not-scheduled). Error monitoring/alerting IS available (opt-in, disabled by default): see [Error Monitoring](../error-monitoring/overview.md).
- Free tiers on the providers above typically have cold-start latency, storage caps, and request-volume limits not suitable for real production traffic: treat this section as a starting point for a demo/side-project deployment, not a scaling plan.
