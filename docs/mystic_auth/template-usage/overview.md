# Using This Repository as a Template
---

## What this template provides

This template ships the authenticated app shell (sidebar, top bar, and the auth/PBAC/audit-log pages listed below) plus a minimal pre-auth landing page at `/` (`frontend/src/app/landing_page/LandingPage.tsx`, mounted in `frontend/src/app/App.tsx`) that redirects an already-signed-in visitor straight to `/dashboard`. It's a worked example of the "outside the auth shell" page shape, not a page meant to ship as-is - rename, restyle, or replace it freely (see [worked example §6](worked-example.md#6-a-pre-auth-landing-page)).

- **Authentication**: email+password with Argon2 hashing, email verification, rate limiting + brute-force lockout, Google OAuth2 (PKCE), JWT access+refresh tokens as httpOnly cookies, refresh-token rotation with reuse detection, logout/logout-all, forgot/reset password. See [Authentication Overview](../authentication/overview.md).
- **Authorization**: Policy-Based Access Control (PBAC). Every protected route is gated by an assigned `Policy`, not by a user's `role`. Policies are data (rows in Postgres), so a new access rule is a new policy, not a new deploy. See [PBAC Architecture](../authorization/architecture/README.md).
- **Audit logging**: two append-only tables: security/session events, and every PBAC allow/deny decision. See [Database Design](../database/design.md#why-two-audit-tables-not-one).
- **Frontend**: React 19 + TypeScript, Vite, Tailwind v4 + shadcn/ui (Radix primitives), Zustand, and TanStack Query. See [Frontend Architecture](../architecture/frontend.md).
- **Infrastructure**: Docker Compose (dev + prod), PostgreSQL, Valkey, Procrastinate async email (Postgres-native, no separate broker), Alembic migrations, GitHub Actions CI.
- **Error monitoring**: self-hosted Bugsink, on by default with the stack. See [Error Monitoring](../error-monitoring/overview.md).

---

## Get started

New clone, first time here? Start with **[Quickstart](quickstart.md)**: the one-command path from `git clone` to a working login, each step run by hand instead, keeping env files honest over time, and setting up Google OAuth and email.

Already set up and just need a reminder of which script does what? See the **[Command Cheat Sheet](cheatsheet.md)**.

---

## The `app/` + `mystic_auth/` split

Every file in the repo falls into exactly one of three ownership tiers, so a future `sync-upstream.sh` run stays low-conflict. See **[The `app/` + `mystic_auth/` Split](ownership-split.md)** for the full tiering table and diagram.

The shortest rule is: put product code in an `app` tree, consume MysticAuth through its SDK, and keep template internals unchanged. For a backend feature, that normally means `backend/app/<feature>/` plus an app-owned migration, policy, settings field in `backend/app/core/settings.py`, and tests under `tests/backend/app/` (create a test subdirectory only when the feature needs several test files). For a frontend feature, use `frontend/src/app/<feature>/` and import shared template capabilities from `frontend/src/app/sdk.ts`. Put deployment-specific values in the matching `env/app/.env.<mode>` file and Compose overrides in `docker/app/compose/`.

The setup and sync scripts may create, refresh, or preserve the upstream runtime files under
`env/mystic_auth/` because the template still owns its required authentication and infrastructure
configuration. That is automation and deployment state, not a downstream customization location:
product code, product settings, product secrets, integrations, tests, scripts, and Compose changes
belong in the corresponding `app/` trees. Downstream users should not hand-edit `mystic_auth/`
source files or tracked `.example` files.

Background work follows the same split. Put downstream tasks and lifecycle
observers under `backend/app/`, list their import modules in the app-owned env
file, and consume the supported task APIs from `app.sdk`. This lets a future
upstream sync replace `backend/mystic_auth/` without requiring edits to task
registration internals. See [Background-task extensions](../background-workers/procrastinate.md#downstream-task-and-worker-extensions).

Integration credentials follow the same boundary: product secret providers
belong under `backend/app/` (with tests under `tests/backend/app/`), while
Mystic Auth supplies only the generic provider contract through `app.sdk`.
Downstream projects never edit `backend/mystic_auth/`. See [Downstream
Integration Secrets](../security/integration-secrets.md).

If you are starting from a fresh clone, follow this order: [Quickstart](quickstart.md) → [ownership split](ownership-split.md) → the [first-feature tutorial](customization.md#first-feature-tutorial) → [launch checklist](downstream-launch-checklist.md). That path tells you what to copy, what to edit, and what must remain upstream-owned.

---

## Building on this template

New domain/resource, database changes, PBAC route protection, replacing the frontend entirely: see **[Building On This Template](customization.md)**.

---

## Deployment

See the [Deployment Guide](../deployment/guide.md) for Compose topology, required env vars, migrations, backups, and production host requirements. Use one of the [`docker-compose.local-prod-*.yml`](../deployment/local-prod/README.md#which-tunnel-do-i-want) variants for a production-style local or self-hosted run behind a free tunnel. Use [`docker-compose.prod.yml`](../../../docker/mystic_auth/compose/docker-compose.prod.yml) for self-hosting on your own server, where Caddy terminates TLS.

Before a customized downstream project goes to real users, follow the
[Downstream Project Launch Checklist](downstream-launch-checklist.md). It
covers project-specific legal, integration, VPS, backup, monitoring,
accessibility, and acceptance work that does not belong in the reusable
template's own setup.

---

## Staying in sync with upstream template updates

Pulling in fixes/features from the original template once your own project has diverged from it now lives in its own doc, including the full step-by-step walkthrough and a worked conflict-resolution example: see [Staying in Sync with Upstream Template Updates](syncing-upstream/README.md).

---

## Where to go next

- New to the codebase? Start at [`docs/mystic_auth/README.md`](../README.md) for the full index.
- Building a protected feature? [Adding New Permissions](../authorization/adding-permissions.md), protect the route as shown in [Building On This Template](customization.md#pbac-usage), then [Writing and Testing Policies](../authorization/writing-testing-policies.md).
- Something not behaving as documented? [PBAC Troubleshooting](../authorization/troubleshooting/README.md).

---

## Getting help

Search [existing Issues](https://github.com/Nachiket-2024/mystic-auth/issues) first, then open a new one with clear repro steps. PRs welcome. **Found a security vulnerability?** Don't open a public Issue: see [SECURITY.md](../../../SECURITY.md).

---
