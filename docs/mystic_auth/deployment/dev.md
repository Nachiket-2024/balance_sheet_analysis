# Dev Deployment

Local development: hot reload on both backend and frontend, source
bind-mounted from the host, no TLS. This is the mode you use day to day
while writing code. Start here if you're new to the repo.

Not sure this is the mode you want? See the
[dev vs. local-prod vs. prod comparison](guide.md#at-a-glance) in the
Deployment Guide.

---

## Getting started

**Step 1: Copy the env file.**

```bash
cp .env.example .env
```

`.env.example` is the dev template for `docker-compose.yml`. Its defaults
are enough to boot the stack as-is. It uses localhost URLs, development mode,
Docker service names for internal database and Redis access, and placeholder
third-party credentials.

Use a different template if you are not running dev:

- Local-prod: copy `.env.local-prod.example` and use
  `docker-compose.local-prod.yml`.
- Prod: copy `.env.prod.example` and use `docker-compose.prod.yml`.

See [Choosing the right env template](guide.md#choosing-the-right-env-template)
for the quick comparison.

---

**Step 2: Configure a login path.**

The stack can boot without real Google or SMTP values, but a normal user
cannot finish signup and reach the dashboard until one verification path
works:

- Configure `FROM_EMAIL` and `GMAIL_APP_PASSWORD` to support password signup,
  email verification, and password reset.
- Configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and
  `GOOGLE_REDIRECT_URI` to support Google login. Google login creates a
  verified account because Google has already verified the email.

The CLI-created system superuser is separate from those normal-user paths. It
is marked verified by the script and can sign in with its password without
Google or SMTP. Regular password signups still need email delivery.

See [Environment variables](#environment-variables) below for the runtime
rules, or the [Template Usage Guide](../template-usage/overview.md) for the
full first-run walkthrough (cloning, `.env`, first `docker compose up`).

---

**Step 3: Start the stack.**

```bash
./scripts/docker/dev-up.sh      # Git Bash, WSL, Linux, macOS
```

```powershell
.\scripts\docker\dev-up.ps1     # PowerShell
```

```bat
scripts\docker\dev-up.cmd       # Command Prompt
```

The helper starts the stack detached, restarts `backend` and
`taskiq_worker` so their startup banners are fresh, waits for health
checks, then tails logs from `backend`/`frontend`/`taskiq_worker`. See
[Docker Overview: day-to-day dev-up helpers](../docker/overview.md#day-to-day-dev-up-helpers)
for why this is preferred over plain `docker compose up`.

Use plain `docker compose up` (no `-d`) instead when you want every
service's logs interleaved into one stream, e.g. debugging Postgres/Bugsink/
Alembic startup itself rather than the app.

---

**Step 4: Open the app.**

Frontend: [http://localhost:5173](http://localhost:5173)
API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Environment variables

`.env.example` is the source of truth for dev values. It includes localhost
URLs, Docker service names, development mode, and placeholders for Google,
SMTP, and Bugsink.

Dev values are read at container startup. If you change backend, database,
Redis, Google, SMTP, or rate-limit values in `.env`, restart the affected
containers. If you change `VITE_*` values for the Docker frontend dev server,
restart `frontend` so Vite reads the new values.

See [Deployment Guide](guide.md#required-production-environment-variables)
for what changes once you move to local-prod or prod.

---

## Ports

All published to `localhost` for direct access:

| Service | Port |
|---|---|
| frontend (Vite dev server, HMR) | 5173 |
| backend | 8000 |
| postgres | 5433 |
| redis | 6380 |
| bugsink | 8010 |

---

## What's different from local-prod / prod

- Source code is bind-mounted (`./backend:/app`, `frontend/`), not baked
  into the image. Edits take effect immediately.
- `backend`/`taskiq_worker` run with `--reload`.
- No `restart:` policy beyond Postgres/Redis. You restart manually.
- No `alembic: service_completed_successfully` gate on `backend` startup.
- No Cloudflare Tunnel, no Caddy: everything is `localhost`-only, no public
  entrypoint.

See [Docker Overview: dev vs. production compose](../docker/overview.md#dev-vs-production-compose)
for the full service-by-service comparison across all three Compose files.

---

## Stopping

```bash
docker compose down
```

Add `-v` to also drop the Postgres/Redis volumes (wipes local data).
