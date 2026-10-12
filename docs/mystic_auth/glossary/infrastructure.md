# Glossary: Infrastructure
---

Database, backend framework, background jobs, deployment, and HTTP security terms. See [Glossary](README.md) for the full index.

---

## Postgres

The relational database that is this app's actual system of record: user accounts, policies, sessions, audit logs, and even the background job queue (Procrastinate) all live in the same Postgres instance. See [Database Design](../database/design.md).

---

## Valkey

An in-memory data store used here for anything that needs to be fast and short-lived: the PBAC policy cache, rate-limit counters, session version counters (`account_ver`/`chain_ver`), OAuth2 state/PKCE storage, and Pub/Sub events. It is not the system of record; Postgres is.

---

## Valkey Pub/Sub

A Valkey feature where one process publishes a message on a named channel and every other process subscribed to that channel receives it instantly. This app uses it to fan out session and permission-change events to every open SSE connection for an account. See [Session Management: Real-time push](../authentication/session-management/real-time-push.md#real-time-push).

---

## cache-aside

A caching pattern where the application asks the cache first, falls back to the durable source of truth on a miss, then writes the fresh value back into the cache for the next request. In this app, PBAC policy reads use Valkey as a cache-aside layer over Postgres. Valkey can be empty or unavailable and Postgres still remains the source of truth.

---

## TTL

Short for Time To Live: how long a cached or stored value is allowed to live before it's treated as expired and either refreshed or discarded. Used throughout this app for the Valkey policy cache, OAuth2 state, and cached session-chain versions.

---

## Alembic

The migration tool that manages every change to the Postgres schema as a versioned, ordered script (`backend/alembic/versions/`). The app never auto-creates tables on startup; schema changes only happen through an Alembic migration, run once by its own one-shot `alembic` container before `backend`/`procrastinate_worker` start. See [Docker Overview](../docker/overview.md).

---

## SQLAlchemy

The Python library used to talk to Postgres from the backend, mapping database rows to Python objects (an ORM: Object-Relational Mapper) and building queries. Used in its async form (`postgresql+asyncpg://`) so database calls don't block the server.

---

## FastAPI

The Python web framework the backend is built on. It handles routing, request/response validation (via Pydantic models), and dependency injection, which is how things like `get_current_user` and `require_authorization` get attached to routes. Served in production by Uvicorn (an ASGI server).

---

## Pydantic

The Python library FastAPI uses to define and validate request/response shapes as typed models. A request that doesn't match a route's Pydantic model is rejected automatically, before the route's own code runs.

---

## middleware

Code that runs on every request/response, wrapped around the actual route handler. This app stacks several: CORS, request logging, security headers, and a correlation-id tagger, in a specific order that matters (see [Security Hardening: Middleware ordering](../security/hardening-http.md#middleware-ordering)).

---

## Procrastinate / background worker

Procrastinate is the Postgres-backed job queue this app uses to run work outside the request/response cycle, such as sending emails and account-lifecycle events, so a slow SMTP call or listener never makes an API response wait on it. A separate `procrastinate_worker` process picks up queued jobs and runs scheduled tasks for account purge, audit-log anonymization, expired-session and refresh-claim cleanup, and lifecycle-outbox reconciliation. See [Background Email Delivery](../background-workers/procrastinate.md).

---

## periodic task / cron-style job

A task Procrastinate runs automatically on a recurring schedule (for example, daily), rather than being enqueued by a specific request. Account purge, audit-log anonymization, session and refresh-claim cleanup, and lifecycle-outbox reconciliation run inside the same `procrastinate_worker` process as on-demand delivery jobs, with no separate scheduler process. See [Background Email Delivery](../background-workers/procrastinate.md).

---

## Docker Compose

The tool used to define and run this app's multiple containers (Postgres, Valkey, backend, frontend, worker, and more) together as one stack, with a different Compose file per deployment mode (dev, local-prod, prod). See [Docker Overview](../docker/overview.md).

---

## Vite

The frontend build tool and dev server. In dev mode it serves the React app with hot module reloading; in production it's used to produce the static build that nginx serves. See [Docker Overview](../docker/overview.md).

---

## nginx

The web server that serves the frontend's production static build and proxies requests, used only in local-prod and prod deployment modes (dev uses the Vite dev server directly instead). See [Docker Overview](../docker/overview.md).

---

## Caddy

The web server used in the standard production deployment mode to terminate TLS in front of the app, automatically obtaining and renewing certificates via Let's Encrypt. See [Prod Deployment](../deployment/prod.md).

---

## tunnel (Cloudflare / ngrok / Tailscale Funnel)

A way to expose a locally-running stack to the public internet without needing a server with a public IP or DNS of your own; the tunnel provider terminates TLS at their edge and proxies traffic back to your machine. This app supports four interchangeable tunnel options for its "local-prod" deployment mode: Cloudflare Quick Tunnel, Cloudflare Named Tunnel, ngrok, and Tailscale Funnel. See [Local-Prod Deployment](../deployment/local-prod/README.md#which-tunnel-do-i-want).

---

## Cloudflare Quick Tunnel

The zero-setup local-prod tunnel option: no Cloudflare account or domain needed, up in under a minute, but the public URL is random and changes on every restart. Good for a quick test, not for anything where you need to configure a stable callback URL (like Google OAuth2). See [Cloudflare Quick Tunnel](../deployment/local-prod/cloudflare-quick-tunnel.md).

---

## Cloudflare Named Tunnel

A local-prod tunnel option that gives you a stable public URL under a domain you own, routed through `cloudflared` and a free Cloudflare account. Needs a domain whose DNS zone lives in that same Cloudflare account, since Cloudflare resolves a tunnel by matching the request against that account's own Public Hostname configuration. See [Cloudflare Named Tunnel](../deployment/local-prod/cloudflare-named-tunnel.md).

---

## ngrok

A local-prod tunnel option using a free ngrok account and its free static domain, giving a stable public URL from the first boot (no separate "quick" zero-account mode like Cloudflare has). See [ngrok Tunnel](../deployment/local-prod/ngrok-tunnel.md).

---

## Tailscale Funnel

A local-prod tunnel option built on a free Tailscale account and an auth key, giving a stable public URL from the first boot. It doubles as a private network (a "tailnet") to the rest of the stack for your own other devices, tunnel or no tunnel. See [Tailscale Funnel](../deployment/local-prod/tailscale-funnel.md).

---

## reverse proxy

A server that sits in front of an application and forwards incoming requests to it, often also handling TLS termination, load balancing, or static-file serving. Caddy, nginx, and each tunnel provider all act as a reverse proxy somewhere in this app's deployment modes.

---

## trusted proxy / X-Forwarded-For

When a request passes through a reverse proxy, the proxy typically sets an `X-Forwarded-For` header naming the original client IP, since the app otherwise only sees the proxy's own IP. This app only trusts that header's value when the immediate connecting peer is explicitly listed in `TRUSTED_PROXY_IPS`; otherwise it uses the literal TCP peer address, so a client can't simply forge the header to spoof their IP. See [Authorization Architecture: Authorization Context Builder](../authorization/architecture/component-responsibilities.md#authorization-context-builder).

---

## IP spoofing (client IP)

Deliberately sending a false client IP, most commonly by forging the `X-Forwarded-For` header. This app's trusted-proxy check (above) is the specific defense against it for rate limiting, lockout, and audit logging.

---

## CORS

Short for Cross-Origin Resource Sharing: the browser rule that blocks a web page from calling an API on a different origin (domain/port) unless that API explicitly allows it. The backend's CORS configuration is what lets the frontend's dev server or production domain call it at all. See [Security Hardening: HTTP Layer](../security/hardening-http.md#cors).

---

## CSP (Content Security Policy)

A response header that tells the browser which sources of scripts, styles, and other content a page is allowed to load, blocking anything else even if injected by an attacker. This API sends a maximally strict policy (`default-src 'none'`) everywhere except its own auto-generated API docs pages, which need a relaxed policy to load their own assets. See [Security Hardening: HTTP Layer](../security/hardening-http.md#security-response-headers).

---

## HSTS (Strict-Transport-Security)

A response header that tells the browser to only ever contact this domain over HTTPS, never plain HTTP, for a set period of time. Sent only in production, since forcing it on in a non-production environment served over plain HTTP would have no way to be undone short of a code change. See [Security Hardening: HTTP Layer](../security/hardening-http.md#security-response-headers).

---

## backup / restore

The scheduled, automatic custom-format dump of both the app's and Bugsink's Postgres databases to local files, handled by the `db_backup` container running on a loop in every production-style Compose file. Each dump is verified with `pg_restore --list` before the job reports success. See [Deployment Guide: Backups](../deployment/migrations-and-backups.md).

---

## VPS

Short for Virtual Private Server: a rented virtual machine with its own CPU,
memory, storage, network address, and operating system. The production Compose
mode can run on one VPS, but the template does not provision or manage that
server for you.

---

## DNS

The system that maps a human-readable hostname such as `auth.example.com` to
an IP address. Production deployment needs DNS pointed at the public entrypoint
before Caddy or another TLS provider can issue a certificate.

---

## TLS

Transport Layer Security, the encryption protocol used by HTTPS. A TLS
terminator such as Caddy or a tunnel provider accepts the encrypted connection,
then forwards a protected or private connection to the application.

---

## PITR

Short for point-in-time recovery. A database recovery method that combines a
base backup with continuous write-ahead-log archiving so an operator can restore
to a chosen time. The template's default scheduled `pg_dump` files do not
provide PITR.

---

## SBOM

Short for Software Bill of Materials: a machine-readable inventory of packages
included in a built artifact. CI generates SPDX JSON SBOMs for the exact
backend, frontend, and database-backup runtime images it builds, then stores
them as a 90-day artifact. An SBOM is an inventory for vulnerability
response; it is not a signature, proof that an image is safe, or a backup.

---

## off-host backup

A backup stored outside the machine that runs the application, such as an
encrypted object-storage bucket, another server, or removable media. It is what
protects against loss of the VPS or its local disk. See [Migrations and
Backups](../deployment/migrations-and-backups.md#6-off-host-copy-without-a-cloud-account).

---

## monitoring and alerting

Monitoring collects health signals such as uptime, disk space, container
health, certificate expiry, and backup age. Alerting sends a human a warning
when a signal crosses a useful threshold. Bugsink reports application errors,
but it does not replace host, backup, or provider monitoring.

---

## environment variable

A named setting supplied to a process by the shell or Docker Compose. The
backend reads its declared settings through `core/settings.py`; the frontend
reads `VITE_*` values at Vite build/start time; some Compose services read
additional variables directly. See [Environment Configuration](../environment/README.md).

---

## healthcheck

A Docker Compose mechanism where a container reports whether it's actually ready to serve traffic, not just running. This app uses healthchecks to sequence startup correctly, e.g. making `backend` wait until `postgres` and `valkey` are healthy before it starts.

---

## CI (Continuous Integration)

Automated checks that run on every push and pull request, defined in `.github/workflows/ci.yml` (GitHub Actions). This app's CI runs backend lint/type-check/tests, frontend lint/type-check/tests, a secrets scan, and a Docker build-and-smoke-test, all independently. See [CI/CD Overview](../cicd/overview.md).

---

## linting / type-checking

Automated static analysis that catches style issues and, separately, type errors before code ever runs. The backend uses `ruff` (lint) and `mypy` (types); the frontend uses ESLint and the TypeScript compiler. Both run as their own CI steps so a failure names the specific tool that caught it.

---

## bandit / pip-audit

Two backend security-focused CI checks: `bandit` scans the backend's own Python code for common security anti-patterns; `pip-audit` checks installed dependencies against known-vulnerability databases (CVEs). See [CI/CD Overview](../cicd/overview.md).

---

## gitleaks / secrets scan

A CI job that scans the entire git history (not just the current diff) for accidentally committed secrets like API keys or passwords, failing the build if it finds one. See [CI/CD Overview](../cicd/overview.md).

See [Testing](testing.md) for unit/integration/performance/coverage-gate terms specific to the test suites themselves, and [Local Scripts & Dev Tooling](tooling.md) for the dev-up/backend-exec helper scripts.

---
