# System Architecture

High-level overview of the whole stack. For the PBAC authorization pipeline specifically, see [../authorization/architecture.md](../authorization/architecture.md); for deployment/runtime topology, see [../deployment/guide.md](../deployment/guide.md).

## Components

```mermaid
flowchart TD
    Browser["Browser (SPA)"]

    Browser -- "HTTPS (TLS terminated<br/>in front: see<br/>deployment/guide.md)" --> Nginx
    Browser -- HTTPS --> Backend

    Nginx["nginx<br/>(static frontend build)"]
    Backend["FastAPI backend<br/>(uvicorn)"]

    Backend --> Postgres[("PostgreSQL<br/>users, policies,<br/>audit logs")]
    Backend --> Redis[("Redis<br/>rate limits, account/chain<br/>version counters, reset/verify<br/>tokens")]
    Backend --> Bugsink["Bugsink<br/>(self-hosted error monitoring,<br/>own DB on same Postgres server)"]
    Browser -. "unhandled errors" .-> Bugsink

    Redis <--> Taskiq["Taskiq worker<br/>(async email sending,<br/>same Redis as broker)"]
```

- **Frontend**: React + TypeScript + Chakra UI + Zustand (client state) + TanStack Query (server state). Built as a static SPA, served by nginx in production-style Compose files or Vite's dev server locally (`docker-compose.yml`).
- **Backend**: FastAPI, async throughout (SQLAlchemy async engine, async Redis client). One process type (`backend/app/main.py`), shared by the `backend`, `taskiq_worker`, and `alembic` containers via the same Docker image (`docker/backend.Dockerfile`) with different `command:` overrides.
- **PostgreSQL**: system of record: users, policies, policy history, both audit log tables (authorization decisions and security events).
- **Redis**: ephemeral/derived state only, never the source of truth for anything that must survive a flush: rate-limit/lockout counters, the account/chain token-version counters (logout-all and single-session revocation), single-use refresh-token rotation claims, single-use password-reset/email-verification/OAuth2-state tokens (all with TTLs matching their expiry). Also Taskiq's broker/result backend.
- **Email queue**: uses Taskiq and Redis. Auth flows enqueue email jobs with `send_email_task.kiq(...)`, and the `taskiq_worker` sends them through the configured SMTP sender.
- **Bugsink**: self-hosted error monitoring, enabled by default: starts with the stack alongside everything else. Backend and frontend both report unhandled exceptions to it over the Sentry SDK wire protocol. Runs as its own container, using a second database on the same Postgres server (not a second Postgres instance). See [Error Monitoring](../error-monitoring/overview.md).

---

## Why this split

- **Redis vs. Postgres**: everything in Redis is either a cache, a rate/lockout counter, or a single-use token: losing it on a restart degrades gracefully (a user re-requests a password reset; a rate limit resets) rather than corrupting state. Nothing that needs to survive indefinitely (users, policies, audit history) lives there.
- **Queued email**: email delivery is the one slow, failure-prone I/O call in the auth flows. Queuing it means signup and password-reset requests are not held open waiting on SMTP. Taskiq fits this stack because Redis and a worker already run in Docker and self-hosted deployments.
- **One backend image, three roles**: `backend`, `taskiq_worker`, and `alembic` all run from `docker/backend.Dockerfile` with different commands, rather than three separate images: keeps dependency versions/code identical across all three by construction, at the cost of the worker/alembic containers also containing an unused `uvicorn` entrypoint they never run.

---

## Request lifecycle (authenticated request)

```mermaid
sequenceDiagram
    participant B as Browser
    participant M as Middleware
    participant D as get_current_user /<br/>require_authorization
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

1. Browser sends a request with `access_token`/`refresh_token` httpOnly cookies (never accessible to frontend JS: see [Authentication Flows](../authentication/overview.md)).
2. `SecurityHeadersMiddleware` and `CorrelationIdMiddleware`/`LoggingMiddleware` wrap every request (see `backend/app/main.py`, `backend/mystic_auth/auth/security/`, `backend/mystic_auth/logging/`).
3. `Depends(get_current_user)` (or, for a specific action, `Depends(require_authorization(action, resource_type))`) verifies the JWT, re-queries the user row (so a since-deactivated/deleted account is rejected even with a still-valid, unexpired token: see [Security Decisions](../security/decisions.md#why-current-user-lookups-re-query-the-database-every-time)), and resolves the caller's current PBAC permissions from their assigned policies.
4. On a 401 specifically, `frontend/src/mystic_auth/auth/session_lifecycle/setupAuthInterceptor.ts` attempts one silent refresh-and-retry before giving up and marking the session invalid: see [Authentication Flows](../authentication/overview.md#refresh-token-rotation).
5. The route handler runs, using `authorization_service.authorize()`/`.require()` for any access decision beyond "is there a valid session": every such call also writes an audit log row (allow or deny).

---

## Database design

See [../database/design.md](../database/design.md) for the schema itself (tables, columns, foreign keys, and why several audit tables deliberately store `user_email` as a snapshot string rather than a foreign key).
