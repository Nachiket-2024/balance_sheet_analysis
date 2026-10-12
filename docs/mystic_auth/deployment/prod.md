# Prod Deployment
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

Self-hosted deployment for your own server. This can be a virtual private
server, cloud instance, bare-metal server, or any host with a public IP. The
Compose stack owns the public HTTP/HTTPS entrypoint through Caddy, which
terminates TLS with automatic Let's Encrypt certificates. Use this instead of
[Local-Prod](local-prod/README.md) when traffic should reach the server directly
rather than route from your own machine through a tunnel. If you do
not have a public server, see [Local-Prod Deployment](local-prod/README.md) instead.

Not sure this is the mode you want? See the
[dev vs. local-prod vs. prod comparison](guide.md#1-deployment-modes) in the
Deployment Guide.

Use the `prod-up` helper when possible: it passes both the upstream and
app-owned Compose/env files. For a manual `docker compose` command, always
include `docker/app/compose/docker-compose.prod.yml` and
`--env-file env/app/.env.prod` after their `mystic_auth` counterparts so your
downstream services and settings are loaded.

---

## Getting started

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    S1["Step 1: Confirm prerequisites\npublic IP, DNS already pointed,\nSMTP access, OAuth creds if used"]
    S2["Step 2: Copy env.prod.example,\nfill in domain vars,\nrotate secrets"]
    Check["check-env.sh env/mystic_auth/.env.prod\ncatches placeholder secrets,\nport conflicts"]
    S3["Step 3: docker compose\n-f docker-compose.prod.yml up -d --build"]
    Geo{"Session geolocation\nwanted?"}
    S3b["Step 3b: re-run with\n--profile geoip"]
    S4["Step 4: open https://PUBLIC_DOMAIN\nCaddy issues the TLS cert\non first request"]

    S1 --> S2 --> Check --> S3 --> Geo
    Geo -- "yes" --> S3b --> S4
    Geo -- "no" --> S4

    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    classDef caution fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef terminal fill:#dcfce7,stroke:#16a34a,color:#14532d
    class Geo decision
    class Check caution
    class S4 terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

---

**Step 1: Confirm prerequisites.**

- A host that can run Docker Compose continuously, with a public IP.
- A domain whose DNS already points at that host's public IP, required
  *before* first start, or certificate issuance fails.
- Network access for SMTP email delivery.
- Google OAuth2 credentials if Google login is enabled.

---

**Step 2: Copy the env file and fill in your domain.**

```bash
cp env/mystic_auth/.env.prod.example env/mystic_auth/.env.prod
```

Or run `scripts/mystic_auth/env-tools/setup-env/setup-env.sh` (`.ps1`/`.cmd`) instead: it does
this copy (and every other mode's) in one pass, generating a distinct
random secret per password field, so most of "Also rotate ..." below is
already done for a freshly created file.

`env/mystic_auth/.env.prod.example` and `env/app/.env.prod.example` are the prod templates for the upstream Compose file and its app-owned override, `docker/mystic_auth/compose/docker-compose.prod.yml` plus `docker/app/compose/docker-compose.prod.yml`.
`ENVIRONMENT=production` and empty `VITE_API_BASE_URL` are already set correctly for
the bundled Caddy to frontend nginx to backend route. `TRUSTED_PROXY_IPS` isn't set
directly there - `docker-compose.prod.yml` derives it from `FRONTEND_STATIC_IP`/
`CADDY_STATIC_IP` (also in that file), so it can't drift out of sync with the actual
pinned addresses.

Before starting, replace every `<your-domain>` placeholder in the copied
`env/mystic_auth/.env.prod` with your real domain:

- `PUBLIC_DOMAIN`
- `FRONTEND_BASE_URL`
- `BACKEND_BASE_URL`
- `JWT_ISSUER` and `JWT_AUDIENCE`, minted into every access/refresh/verify
  JWT and checked back on `verify_token()`; leaving these at the
  `<your-domain>` placeholder breaks every login
- `GOOGLE_REDIRECT_URI`, if Google login is enabled
- `BUGSINK_BASE_URL`, if Bugsink is publicly routed

Also rotate before starting:

- `SECRET_KEY`, `POSTGRES_PASSWORD`, `BUGSINK_SECRET_KEY`, and `BUGSINK_SUPERUSER_PASSWORD`.
- `VALKEY_PASSWORD` is required. `setup-env` generates it and embeds it in `VALKEY_URL`; production Compose refuses to start if it is missing - see [Valkey authentication](../security/hardening-infra.md#valkey-authentication).
- `APP_DATABASE_URL`'s password alongside `DATABASE_URL`'s, if you keep the least-privilege app role enabled (the default; see [Deployment Guide: Database migrations](migrations-and-backups.md#1-database-migrations)).

Also configure before opening the app to real users:

- SMTP before opening password signup to users, because unverified password accounts cannot log in.
- Google OAuth2 before showing Google login.
- `BACKUP_ENCRYPTION_KEY` and `BACKUP_UPLOAD_COMMAND` before starting the
  production-shaped stack. The backup sidecar refuses to start without both;
  use the [off-host backup guide](migrations-and-backups.md#backblaze-b2-off-host-copies)
  to configure the upload command in the gitignored runtime env file.
- The CLI-created system superuser can sign in without Google or SMTP because the script marks it verified. See [System Superuser](../authentication/system-superuser/README.md) for the interactive command, or `local-scripts/mystic_auth/prod/create-system-user.*` for a non-interactive version (fill in non-dev credentials, not the dev placeholder).

See also
[Environment variables](#environment-variables) below for the runtime rules and
[Choosing the right env template](environment.md#1-choosing-the-right-env-template)
for the mode comparison.

---

**Step 3: Start the stack.**

Run `scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.prod` (`.ps1`/`.cmd`) first.
It fails if a secret in that file still equals the shipped placeholder
while `ENVIRONMENT=production`, and warns on any remaining `<your_...>`
placeholder or a host port already in use, before you spend a `--build`
finding out the hard way. It also fails early if `BACKUP_ENCRYPTION_KEY` or
`BACKUP_UPLOAD_COMMAND` is blank, or if the upload command does not reference
`$DUMP_FILE`; this prevents Compose interpolation from being the first place
an incomplete backup configuration is discovered.

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml -f docker/app/compose/docker-compose.prod.yml --env-file env/mystic_auth/.env.prod --env-file env/app/.env.prod up -d --build
```

Only Caddy (ports 80/443) is published to the host. `postgres`, `valkey`,
`backend`, and `frontend` stay reachable container-to-container by service
name. Nothing outside the Docker network can reach them directly.

---

**Step 3b (Optional): Enable session geolocation.**

Setting `GEOIP_DB_PATH`/`GEOIPUPDATE_ACCOUNT_ID`/`GEOIPUPDATE_LICENSE_KEY` in
`env/mystic_auth/.env.prod` alone does nothing: the `geoipupdate` service that downloads the
`.mmdb` file is gated behind the `geoip` Compose profile, skipped by Step 3's
command as written. Re-run Step 3 with the profile added instead:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml -f docker/app/compose/docker-compose.prod.yml --env-file env/mystic_auth/.env.prod --env-file env/app/.env.prod --profile geoip up -d --build
```

Without it, the updater is not started and Manage Sessions' Location column
shows "Unknown". When the profile is enabled, the updater healthcheck now
requires a non-empty database and becomes unhealthy if the download fails. See
[Session Geolocation](../geolocation/overview.md)
for the MaxMind account/license-key setup this depends on.

---

**Step 4: Open the app.**

`https://PUBLIC_DOMAIN`. Caddy issues the TLS certificate on first
request, so the very first load may take a few extra seconds.

---

## How routing works

The frontend container's nginx (`docker/mystic_auth/nginx.frontend.conf`) proxies API
route prefixes (`/auth`, `/audit`, `/users`, `/authorization`, `/health`,
`/rate-limits`) to `backend`. It's pinned to `FRONTEND_STATIC_IP` so the
backend can trust its `X-Forwarded-For` header via `TRUSTED_PROXY_IPS`
(derived from `FRONTEND_STATIC_IP`/`CADDY_STATIC_IP`, see
[Routing: Trusted proxy IPs](routing.md#2-trusted-proxy-ips)).

---

## Environment variables

`env/mystic_auth/.env.prod.example` is the source of truth for prod values. It is set up for
Caddy-managed TLS, same-origin API routing, production mode, and the fixed
frontend nginx proxy IP.

Rotate the secrets in the copied `env/mystic_auth/.env.prod` before real use. Review
`PUBLIC_DOMAIN`, `ACME_EMAIL`, `BUGSINK_PUBLIC_DOMAIN`, `FRONTEND_BASE_URL`,
`BACKEND_BASE_URL`, `GOOGLE_REDIRECT_URI`, SMTP, rate-limit, Valkey, and
error-monitoring values before opening the service.

Build-time values must be final before you run `--build`:

- `VITE_API_BASE_URL`: keep empty for the bundled nginx same-origin proxy.
- `VITE_APP_NAME`: public app name shown in the browser.
- `VITE_SENTRY_DSN`: public browser DSN if frontend error reporting is enabled.
- `VITE_SENTRY_ENVIRONMENT`: frontend environment tag.

Runtime values can be changed with a container restart:

- `PUBLIC_DOMAIN`, `ACME_EMAIL`, and `BUGSINK_PUBLIC_DOMAIN`
- `SECRET_KEY`, `DATABASE_URL`, `POSTGRES_*`, `VALKEY_URL`, and
  `VALKEY_PASSWORD`
- `FRONTEND_BASE_URL`, `BACKEND_BASE_URL`, `GOOGLE_REDIRECT_URI`
- SMTP settings, rate-limit settings, and backend `SENTRY_DSN`

`VITE_API_BASE_URL`, `VITE_APP_NAME`, `VITE_SENTRY_DSN`, and
`VITE_SENTRY_ENVIRONMENT` are baked in at image build time, not read at
container runtime. Set them in `env/mystic_auth/.env.prod` before `--build`, not after. See
[Deployment Guide: required production environment variables](environment.md#5-required-production-review)
for the full explanation of each.

---

## What's different from dev / local-prod

See [Docker Overview: dev vs. production compose](../docker/compose-modes.md#dev-vs-production-compose)
for the full table. Same production image/runtime shape as local-prod (no
bind mounts, no reload, `alembic` gates startup), but Caddy replaces the
tunnel (Cloudflare, ngrok, or Tailscale Funnel) as the public entrypoint and
TLS terminator.

---

## Backups, migrations, graceful shutdown, limitations

These are the same across every Compose file. See
[Deployment Guide](migrations-and-backups.md#1-database-migrations) for migrations, backups
(`scripts/mystic_auth/db/database-backup/database-backup.sh docker-compose.prod.yml`), graceful shutdown, and
known limitations of this deployment approach.

---
