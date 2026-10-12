# Production Host Requirements
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

Host-level requirements and runtime behavior shared by production-shaped deployments.

---

## 1. Graceful shutdown
---

`backend/app/main.py` registers a FastAPI lifespan handler. On shutdown, including `docker stop` and rolling restarts, it disposes the SQLAlchemy connection pool and closes the Valkey client cleanly.

The Procrastinate worker uses the same backend image but a different command. It owns background email delivery, account-lifecycle event delivery, and scheduled account purge, audit-log anonymization, session cleanup, refresh-claim cleanup, and lifecycle-outbox reconciliation jobs.

---

## 2. Minimum host requirements
---

A production deployment needs:

1. A host that can run Docker Compose continuously.
2. Persistent storage for Postgres, Caddy certificates, Bugsink state, and backups.
3. Network access for SMTP delivery.
4. DNS pointing at the public host before starting `docker-compose.prod.yml`.
5. A backup schedule and off-host copy path.
6. Monitoring and alerting appropriate for the deployment.
7. A configured system superuser created through the CLI script.

---

## 3. Included services
---

The production-shaped Compose files include:

| Service | Purpose |
|---|---|
| `backend` | FastAPI API server. |
| `frontend` | nginx static SPA server and same-origin API proxy. |
| `postgres` | Durable data store for users, policies, audit logs, jobs, and Bugsink database. |
| `valkey` | Rate-limit/lockout state, OAuth2 state, authorization cache, Pub/Sub, and a non-authoritative cache of PostgreSQL token versions. |
| `procrastinate_worker` | Email and account-lifecycle delivery; scheduled account purge, audit-log anonymization, expired-session and refresh-claim cleanup, and lifecycle-outbox reconciliation. |
| `alembic` | One-shot migration runner. |
| `bugsink` | Self-hosted error monitoring. |
| `db_backup` | Scheduled dump sidecar. |
| `caddy` or tunnel service | Public TLS entrypoint, depending on deployment mode. |

---

## 4. Deployment limits
---

These are intentional scope boundaries:

1. No infrastructure-as-code module is shipped.
2. No registry push or automated deployment workflow is shipped.
3. No managed Postgres backup integration is assumed.
4. No horizontal-scaling topology is documented as the default.
5. Serverless request-driven backend deployment is out of scope because the worker and database lifecycle are long-running service responsibilities.

---
