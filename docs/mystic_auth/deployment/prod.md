# Prod Deployment

Self-hosted deployment for your own server. This can be a virtual private
server, cloud instance, bare-metal server, or any host with a public IP. The
Compose stack owns the public HTTP/HTTPS entrypoint through Caddy, which
terminates TLS with automatic Let's Encrypt certificates. Use this instead of
[Local-Prod](local-prod.md) when traffic should reach the server directly
rather than route from your own machine through Cloudflare Tunnel. If you do
not have a public server, see [Local-Prod Deployment](local-prod.md) instead.

Not sure this is the mode you want? See the
[dev vs. local-prod vs. prod comparison](guide.md#at-a-glance) in the
Deployment Guide.

---

## Getting started

**Step 1: Confirm prerequisites.**

- A host that can run Docker Compose continuously, with a public IP.
- A domain whose DNS already points at that host's public IP, required
  *before* first start, or certificate issuance fails.
- Network access for SMTP email delivery.
- Google OAuth2 credentials if Google login is enabled.

---

**Step 2: Copy the env file and fill in your domain.**

```bash
cp .env.prod.example .env
```

`.env.prod.example` is the prod template for `docker-compose.prod.yml`.
`ENVIRONMENT=production`, empty `VITE_API_BASE_URL`, and
`TRUSTED_PROXY_IPS=172.28.0.10` are already set correctly for the bundled
Caddy to frontend nginx to backend route.

Before starting, replace every `<your-domain>` placeholder in the copied
`.env` with your real domain:

- `PUBLIC_DOMAIN`
- `FRONTEND_BASE_URL`
- `BACKEND_BASE_URL`
- `GOOGLE_REDIRECT_URI`, if Google login is enabled
- `BUGSINK_BASE_URL`, if Bugsink is publicly routed

Also rotate `SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
`BUGSINK_SECRET_KEY`, and `BUGSINK_SUPERUSER_PASSWORD`. Configure SMTP before
opening password signup to users, because unverified password accounts cannot
log in. Configure Google OAuth2 before showing Google login. The CLI-created
system superuser can sign in without Google or SMTP because the script marks it
verified. See [System Superuser](../authentication/system-superuser.md) for
the interactive command, or `local-scripts/prod/create-system-user.*` for a
non-interactive version (fill in real production credentials, not the dev
placeholder). See also
[Environment variables](#environment-variables) below for the runtime rules and
[Choosing the right env template](guide.md#choosing-the-right-env-template)
for the mode comparison.

---

**Step 3: Start the stack.**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Only Caddy (ports 80/443) is published to the host. `postgres`, `redis`,
`backend`, and `frontend` stay reachable container-to-container by service
name. Nothing outside the Docker network can reach them directly.

---

**Step 4: Open the app.**

`https://PUBLIC_DOMAIN`. Caddy issues the TLS certificate on first
request, so the very first load may take a few extra seconds.

---

## How routing works

The frontend container's nginx (`docker/nginx.frontend.conf`) proxies API
route prefixes (`/auth`, `/audit`, `/users`, `/authorization`, `/health`)
to `backend`. It's pinned to `172.28.0.10` so the backend can trust its
`X-Forwarded-For` header via `TRUSTED_PROXY_IPS=172.28.0.10`.

---

## Environment variables

`.env.prod.example` is the source of truth for prod values. It is set up for
Caddy-managed TLS, same-origin API routing, production mode, and the fixed
frontend nginx proxy IP.

Rotate the secrets in the copied `.env` before real use. Review
`PUBLIC_DOMAIN`, `ACME_EMAIL`, `BUGSINK_PUBLIC_DOMAIN`, `FRONTEND_BASE_URL`,
`BACKEND_BASE_URL`, `GOOGLE_REDIRECT_URI`, SMTP, rate-limit, Redis, and
error-monitoring values before opening the service.

Build-time values must be final before you run `--build`:

- `VITE_API_BASE_URL`: keep empty for the bundled nginx same-origin proxy.
- `VITE_APP_NAME`: public app name shown in the browser.
- `VITE_SENTRY_DSN`: public browser DSN if frontend error reporting is enabled.
- `VITE_SENTRY_ENVIRONMENT`: frontend environment tag.

Runtime values can be changed with a container restart:

- `PUBLIC_DOMAIN`, `ACME_EMAIL`, and `BUGSINK_PUBLIC_DOMAIN`
- `SECRET_KEY`, `DATABASE_URL`, `POSTGRES_*`, `REDIS_URL`, and
  `REDIS_PASSWORD`
- `FRONTEND_BASE_URL`, `BACKEND_BASE_URL`, `GOOGLE_REDIRECT_URI`
- SMTP settings, rate-limit settings, and backend `SENTRY_DSN`

`VITE_API_BASE_URL`, `VITE_APP_NAME`, `VITE_SENTRY_DSN`, and
`VITE_SENTRY_ENVIRONMENT` are baked in at image build time, not read at
container runtime. Set them in `.env` before `--build`, not after. See
[Deployment Guide: required production environment variables](guide.md#required-production-environment-variables)
for the full explanation of each.

---

## What's different from dev / local-prod

See [Docker Overview: dev vs. production compose](../docker/overview.md#dev-vs-production-compose)
for the full table. Same production image/runtime shape as local-prod (no
bind mounts, no reload, `alembic` gates startup), but Caddy replaces
Cloudflare Tunnel as the public entrypoint and TLS terminator.

---

## Backups, migrations, graceful shutdown, limitations

These are the same across all three Compose files. See
[Deployment Guide](guide.md#database-migrations) for migrations, backups
(`scripts/db/db_backup.sh docker-compose.prod.yml`), graceful shutdown, and
known limitations of this deployment approach.
