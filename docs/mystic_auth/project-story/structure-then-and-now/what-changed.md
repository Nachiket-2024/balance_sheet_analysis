# Structure: Then and Now

---

Companion to the [Project Story](../README.md) and [How It Evolved](../timeline/README.md). Those pages
explain why the architecture changed. This page shows what the actual folder structure looked
like right before the Claude Code era started, next to what it looks like today, so the shape of
the change is visible at a glance instead of only described in prose, followed by a summary of
the differences.

The "then" tree lists only files and folders that were actually committed. The "now" tree lists
tracked files plus the current additions present in the repository on 11 October;
it still omits `__pycache__`, `node_modules`, build output, coverage reports, and anything else
covered by `.gitignore`. The "then" tree is the real commit tree at
[`946e384`](../../../..), the last commit of the manual, ChatGPT-assisted era, on 14 April, 2026. The
"now" tree reflects the repository as verified on 11 October, 2026.

---

## Pages

- [Then](folder-tree-then.md): the tree at the last pre-Claude-Code commit.
- [Now](folder-tree-now.md): the tree as it stands today.

---

## What Changed, In Short

- **One package became two, on both sides.** `backend/app/` and `frontend/src/app/` are now thin,
  project-owned shells (entry point plus `sdk.py`/`sdk.ts`, `app_sdk.py`/`app_sdk.ts`, with
  `app_sdk.py` also serving as the backend's app-owned startup hook). All the
  actual feature code moved into `backend/mystic_auth/` and `frontend/src/mystic_auth/`, the
  upstream-owned package a template update can safely overwrite. See
  [Using This Repository as a Template](../../template-usage/overview.md) for the ownership model
  and [Syncing with Upstream](../../template-usage/syncing-upstream/README.md) for how updates flow through
  `scripts/mystic_auth/upstream-sync/sync-upstream.sh`.
- **Role-based access became policy-based.** `authorization/` is a new top-level module: policies,
  conditions, an evaluator, caching, and its own audit log. `role` is now descriptive metadata, not
  the thing access decisions are made from. See [PBAC Architecture](../../authorization/architecture/README.md).
- **New backend modules**: `audit_log/` (security/session audit trail), `emails/` (template
  rendering, sending, address normalization), `error_monitoring/` (Sentry-protocol error
  reporting), and `core/` (settings, shared primitives, and the downstream secret-provider boundary),
  `procrastinate_tasks/` (replaced `taskiq_tasks/`, itself a replacement for the
  original Celery setup), `user_lifecycle/` (self-service deletion, admin purge, and
  durable account-lifecycle events),
  `user_session/` (the Manage Sessions dashboard and real-time session events). `user_crud/` and
  `user_table/` were renamed and merged into `user/`.
- **New frontend modules**: `account_settings/`, `audit_log/`, `authorization/`, `layout/`,
  `permissions/`, `policies/`, `rate_limits/`, `theme/`, `translations/`, `ui/`, `users/` replaced
  the old flat `auth/` plus `dashboard/` plus `store/` layout. Redux was replaced by Zustand
  (client state) and TanStack Query (server state).
- **Docs, tests, and CI did not exist before and now do.** `docs/` (split into project-owned
  `docs/app/` and upstream `docs/mystic_auth/`), `tests/` (mirroring the same split, plus
  `unit/integration/security/performance` suites), and `.github/workflows/ci.yml` are all new. See
  [Testing Overview](../../testing/overview.md).
- **Deployment grew from one Compose file to separate mode files.** Dev, each local-prod tunnel
  variant, and prod now live under `docker/mystic_auth/compose/` (each with an empty
  `docker/app/compose/` override for a fork's own additions), with Dockerfiles under
  `docker/mystic_auth/dockerfiles/`, plus `docker/mystic_auth/Caddyfile`/`docker/app/caddy/`, and `docker/mystic_auth/nginx.frontend.conf`/`docker/app/nginx/`.
  `scripts/` and `local-scripts/` (startup, backup/restore,
  system-user bootstrap, upstream sync) are also new; none of this existed when everything ran
  from a single `docker-compose.yml` with two Dockerfiles.
- **Application dependency notices now ship with the runtime artifacts.** Python notices are
  included in the backend image, and frontend notices are served by the production static image.
  Base-image and `db_backup` dependencies remain a separate inventory.
- **`demo_assets/` became `screenshots/`.**
- **Env tooling and load testing grew into their own scripts.** `scripts/mystic_auth/env-tools/` (quickstart,
  setup-env, check-env, set-env-field, copy-env-values, rotate-secrets, plus its own test suite)
  and `scripts/mystic_auth/load-test/` are new, alongside the existing `scripts/mystic_auth/db/`, `scripts/mystic_auth/docker/`, and
  `scripts/mystic_auth/upstream-sync/`.
- **Agent prompts and more docs sections appeared.** Top-level `agent-prompts/` holds reusable
  prompts for setting up a new project from this template and syncing with upstream. `docs/mystic_auth/`
  gained `environment/` (env file and tooling docs) and `glossary/` (per-area terms glossary), and
  `docker/` gained `tailscale-serve-config.json` and `docker/mystic_auth/dockerfiles/backend-entrypoint.sh`.
  Backup delivery also gained detached HMAC verification, and the current project story records
  the account-lifecycle outbox and downstream integration boundaries.
- **Frontend tests gained an `e2e/` suite** alongside `unit/` and `integration/`, matching the
  Playwright E2E setup added for both `tests/frontend/app/` and `tests/frontend/mystic_auth/`.
- **`scripts/`, `agent-prompts/`, and `local-scripts/` gained the `app/`/`mystic_auth/` split too**,
  matching `backend/`, `frontend/`, `tests/`, `docs/`, and `screenshots/`: your own scripts and
  prompts go under each `app/`, template ones under each `mystic_auth/`.
- **`docker/` and `env/` gained the split last**, the two domains that hadn't. `docker/compose/`,
  `dockerfiles/`, `postgres-init/`, `Caddyfile`, and `nginx.frontend.conf` moved under
  `docker/mystic_auth/`, mirrored by an empty `docker/app/`; `env/` split the same way into
  `env/mystic_auth/` + `env/app/`, with development templates named explicitly
  `.env.dev.example` and runtime copies named `.env.dev`. See
  [The `app/` + `mystic_auth/` Split](../../template-usage/ownership-split.md).
- **The extension boundary became executable, not just documented.** Downstream condition handlers
  and validators live under `backend/app/` and register through `app_sdk.py` and the public
  `sdk.py` API. A fork does not edit `backend/mystic_auth/` to add an application condition type.
- **A root `Makefile`/`make.ps1` appeared, then got the split too.** Both are now two-line entry
  points that `include` (Make) or dot-source (PowerShell) the real targets from
  `makefiles/mystic_auth/` + `makefiles/app/`, so adding your own `make` target never conflicts
  with a future upstream one.

---

See [How It Evolved](../timeline/README.md) for the commit-by-commit path between these two trees.

---
