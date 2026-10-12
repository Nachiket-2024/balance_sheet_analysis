# System Architecture
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Frontend Glossary](../glossary/frontend.md).*

High-level overview of the whole stack. For the PBAC authorization pipeline specifically, see [../authorization/architecture/README.md](../authorization/architecture/README.md); for deployment/runtime topology, see [../deployment/guide.md](../deployment/guide.md).

---

## Components

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Browser["Browser (SPA)"]
    Browser -- "HTTPS\n TLS terminated in front\n see deployment guide" --> Nginx
    Browser -- HTTPS --> Backend
    Nginx["nginx\n (static frontend build)"]
    Backend["FastAPI backend\n (uvicorn)"]
    Backend --> Postgres[("PostgreSQL\n users, policies, audit logs,\n token versions and refresh claims") ]
    Backend --> Valkey[("Valkey\n rate limits, account/chain\n version cache, reset/verify\n tokens")]
    Backend --> Bugsink["Bugsink\n self-hosted error monitoring\n own DB on same Postgres server"]
    Browser -. "unhandled errors" .-> Bugsink
    Backend --> Procrastinate["Procrastinate worker\n (async email sending,\n same Postgres as job queue)"]
    linkStyle default stroke:#334155,stroke-width:2px
```

---

- **Frontend**: React + TypeScript + Tailwind v4 + shadcn/ui (Radix primitives) + Zustand (client state) + TanStack Query (server state). Built as a static SPA, served by nginx in production-style Compose files or Vite's dev server locally (`docker-compose.dev.yml`).
- **Backend**: FastAPI, async throughout (SQLAlchemy async engine, async Valkey client). One process type (`backend/app/main.py`), shared by the `backend`, `procrastinate_worker`, and `alembic` containers via the same Docker image (`docker/mystic_auth/dockerfiles/backend.Dockerfile`) with different `command:` overrides.
- **PostgreSQL**: system of record: users, policies, policy history, both audit log tables (authorization decisions and security events), the Procrastinate job queue (`procrastinate_jobs`), durable token-version counters, and consumed refresh-token claims.
- **Valkey**: ephemeral/derived state only, never the source of truth for anything that must survive a flush: rate-limit/lockout counters and cached account/chain token-version counters (logout-all and single-session revocation), single-use password-reset/email-verification/OAuth2-state tokens (all with TTLs matching their expiry). Durable token versions and refresh-token replay claims live in PostgreSQL.
- **Background jobs**: Procrastinate uses the same Postgres instance as everything else (no Valkey broker). Auth flows enqueue email jobs with `send_email_task.defer_async(...)`, and account lifecycle transitions enqueue downstream listener events. The `procrastinate_worker` handles delivery with retries and runs scheduled account purge, audit-log anonymization, expired-session and refresh-claim cleanup, and lifecycle-outbox reconciliation through its internal periodic-task deferrer; no separate scheduler process exists.
- **Bugsink**: self-hosted error monitoring, enabled by default: starts with the stack alongside everything else. Backend and frontend both report unhandled exceptions to it over the Sentry SDK wire protocol. Runs as its own container, using a second database on the same Postgres server (not a second Postgres instance). See [Error Monitoring](../error-monitoring/overview.md).

---

## Why this split

- **Valkey vs. Postgres**: everything in Valkey is either a cache, a rate/lockout counter, or a single-use token: losing it on a restart degrades gracefully (a user re-requests a password reset; a rate limit resets) rather than corrupting state. Nothing that needs to survive indefinitely (users, policies, audit history, or the background job queue) lives there.
- **Queued email**: email delivery is the one slow, failure-prone I/O call in the auth flows. Queuing it means signup and password-reset requests are not held open waiting on SMTP. Procrastinate fits this stack because Postgres (already the system of record here) is also its job queue: no separate broker infrastructure. See [Security Decisions: Taskiq replaced with Procrastinate](../security/decisions-infra.md#taskiq-replaced-with-procrastinate).
- **One backend image, three roles**: `backend`, `procrastinate_worker`, and `alembic` all run from `docker/mystic_auth/dockerfiles/backend.Dockerfile` with different commands, rather than three separate images: keeps dependency versions/code identical across all three by construction, at the cost of the worker/alembic containers also containing an unused `uvicorn` entrypoint they never run.

---

## Request lifecycle (authenticated request)

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155", "signalColor": "#334155", "actorLineColor": "#334155", "activationBorderColor": "#334155", "labelBoxBorderColor": "#334155", "labelBoxBkgColor": "#e2e8f0", "noteBorderColor": "#334155"}, "themeCSS": ".messageLine0, .messageLine1 { stroke-width: 2px !important; }"} }%%
sequenceDiagram
    participant B as Browser
    participant M as Middleware
    participant D as get_current_user / require_authorization
    participant R as Route handler
    participant DB as PostgreSQL
    B->>M: Request + httpOnly cookies
    M->>M: SecurityHeaders, CorrelationId, Logging
    M->>D: 
    D->>DB: Re-query user row
    DB-->>D: User + assigned policies
    alt token expired (401)
        D-->>B: 401
        B->>B: Silent refresh + retry (once)
    else valid
        D->>R: Caller + permissions resolved
        R->>DB: Access decision (authorize/require)
        DB-->>R: 
        R-->>B: Response
    end
```
---

1. Browser sends a request with `access_token`/`refresh_token` httpOnly cookies (never accessible to frontend JS: see [Authentication Flows](../authentication/overview.md)).
2. `SecurityHeadersMiddleware` and `CorrelationIdMiddleware`/`LoggingMiddleware` wrap every request (see `backend/app/main.py`, `backend/mystic_auth/auth/security/`, `backend/mystic_auth/logging/`).
3. `Depends(get_current_user)` (or, for a specific action, `Depends(require_authorization(action, resource_type))`) verifies the JWT, re-queries the user row (so a since-deactivated/deleted account is rejected even with a still-valid, unexpired token: see [Security Decisions](../security/decisions-auth.md#why-current-user-lookups-re-query-the-database-every-time)), and resolves the caller's current PBAC permissions from their assigned policies.
4. On a 401 specifically, `frontend/src/mystic_auth/auth/session_lifecycle/setupAuthInterceptor.ts` attempts one silent refresh-and-retry before giving up and marking the session invalid: see [Authentication Flows](../authentication/overview.md#refresh-token-rotation).
5. The route handler runs, using `authorization_service.authorize()`/`.require()` for any access decision beyond "is there a valid session": every such call also writes an audit log row (allow or deny).

---

## Database design

See [../database/design.md](../database/design.md) for the schema itself (tables, columns, foreign keys, and why several audit tables deliberately store `user_email` as a snapshot string rather than a foreign key).

---
