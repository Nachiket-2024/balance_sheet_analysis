# Docker: Healthchecks

---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

## Service healthchecks

| Service | Check | Notes |
|---|---|---|
| `postgres` | `pg_isready` | |
| `valkey` | `valkey-cli ping` | |
| `backend` | `GET /health/ready` via a Python one-liner (no curl in the slim image) | Confirms DB + Valkey connectivity, not just process liveness. Budget is 10 retries / 30s start period (~130s total) rather than a tighter 5/10s (~60s): generous headroom for a genuinely cold first boot on modest or shared hardware. This is a secondary hardening, not the fix for the specific bug below: no healthcheck budget helps if the container is actually crash-looping. |
| `frontend` (prod) | `wget` against `/` | |
| `frontend` (dev) | none | Acceptable for local dev: Vite's own dev server failure is immediately visible in the terminal |
| `procrastinate_worker` | `procrastinate --app=mystic_auth.procrastinate_tasks.procrastinate_app.app healthchecks` | Overrides the inherited HTTP healthcheck from `backend.Dockerfile`, since the worker serves no HTTP and would otherwise always report unhealthy. Confirms the DB connection works and the `procrastinate_jobs` table exists, not just process liveness |
| `bugsink` | `GET /health/ready` via a Python one-liner | Same reasoning as `backend`'s own check |
| `alembic` | none | One-shot; `service_completed_successfully` is the signal other services wait on, not a healthcheck |
| `bugsink-seed` | none | One-shot, same shape as `alembic`: creates the Bugsink project/DSN once, then exits 0 |

---

See [Docker Overview](overview.md) for the full service list.

---
