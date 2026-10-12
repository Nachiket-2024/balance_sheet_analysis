# Documentation
---

Documentation for this full-stack authentication and PBAC template, organized by feature and runtime ownership. The structure mirrors the code layout under `backend/mystic_auth/<domain>/` and `frontend/src/mystic_auth/<domain>/`.

This is the template's own reference documentation, belonging to upstream and not yours to edit. Your own project's docs go in [`docs/app/`](../app/README.md) instead, so they never conflict with a future `scripts/mystic_auth/upstream-sync/sync-upstream.sh` run. See [Using This Repository as a Template: the `app/` + `mystic_auth/` split](template-usage/ownership-split.md) for the full reasoning.

New to a term you see in these docs? Check the [Glossary](glossary/README.md) first.

Read the docs in this order if you are new to the repository:

1. [Quickstart](template-usage/quickstart.md): get it running first, one command, before reading anything else
2. [System Overview](architecture/system-overview.md)
3. [Authentication Overview](authentication/overview.md)
4. [Authorization Architecture](authorization/architecture/README.md)
5. [Deployment Guide](deployment/guide.md)
6. [Testing Overview](testing/overview.md)

---

## Documentation conventions

- [Documentation Style](documentation-style.md): page structure, numbered procedure style, Mermaid label rules, code reference conventions, and tutorial section format.

---

## Architecture

- [System Overview](architecture/system-overview.md): whole-stack component diagram, why the stack is split this way, request lifecycle
- [Backend Architecture](architecture/backend.md): `backend/mystic_auth/` module layout, request pipeline, middleware
- [Frontend Architecture](architecture/frontend.md): `frontend/src/mystic_auth/` module layout, state management, routing, theming
- [Implementation Coverage Map](architecture/code-map.md): where each major backend, frontend, test, script, Docker, and env directory is documented, including important edge cases

---

## Authentication

- [Authentication Overview](authentication/overview.md): JWT/cookie mechanics, refresh-token rotation, current-session lookups, and links to every flow below
- [Signup and Email Verification](authentication/signup-and-verification.md): account creation, verification token issue/redeem, resend
- [Login](authentication/login.md): rate limiting, brute-force lockout, timing-attack resistance
- [Logout and Logout-All](authentication/logout.md): single-device vs. whole-account session termination, idempotency
- [Password Reset and Password Change](authentication/password-reset.md): forgot-password flow, self-service and permission-protected password change
- [Session Management](authentication/session-management/README.md): active-session tracking, refresh-token rotation mirror, dashboard card behavior, revoke edge cases
- [Account Deletion and Purge](authentication/account-deletion/README.md): self-service delete, permission-protected delete/reactivate/purge, and the scheduled grace-period purge job
- [OAuth2 / PKCE](authentication/oauth2-pkce.md): Google OAuth2 login flow, PKCE code-challenge mechanics, CSRF state protection
- [System Superuser: Bootstrapping and Promotion](authentication/system-superuser/README.md): `create_system_user.py`'s full behavior, covering fresh creation, promoting an existing account, and the Google-only-account special case

---

## Authorization (PBAC)

- [Architecture Overview](authorization/architecture/README.md): request flow, component responsibilities, integration points
- [Policy JSON Examples](authorization/policy-examples.md): basic, conditioned, superuser, and self-service policies
- [Unconditioned Policy Quickstart](authorization/unconditioned-policy-quickstart.md): plain role-shaped access (no conditions) using the same policies, for projects that don't need PBAC's full generality
- [Common Patterns](authorization/common-patterns.md): modeling common access shapes (e.g. org-chart/company-group hierarchies) on top of PBAC's existing condition types
- [Condition Schema Reference](authorization/condition-schema-reference.md): every supported condition type, field-by-field
- [Adding New Permissions](authorization/adding-permissions.md): extending the action vocabulary
- [Adding New Condition Handlers](authorization/adding-condition-handlers.md): extending the condition framework
- [Writing and Testing Policies](authorization/writing-testing-policies.md): policy lifecycle, local testing, unit test patterns
- [Operational Troubleshooting Guide](authorization/troubleshooting/README.md): common issues, logging, Valkey/DB debugging

---

## Database

- [Database Design](database/design.md): schema, foreign keys, account lifecycle (soft delete/purge/reactivate)

---

## API

- [API Reference](api/reference.md): route inventory grouped by domain, request/response shapes, auth requirements

---

## Background Email Delivery

- [Background Email Delivery](background-workers/procrastinate.md): Procrastinate worker setup, downstream task/lifecycle extensions, Postgres-backed job queue, backoff retries, failure handling

---

## Security

- [Security Decisions](security/decisions.md): index of the *why* behind non-obvious security choices, plus known accepted gaps, split into [Auth & Session](security/decisions-auth.md), [Infrastructure](security/decisions-infra.md), and [Product](security/decisions-product.md)
- [Security Hardening](security/hardening.md): rate limiting, lockout, security headers, CORS, cookie flags, consolidated
- [Rate Limits](security/hardening-abuse-prevention.md#rate-limiting): the generic per-IP/per-account limiter, brute-force lockout, and the permission-protected Rate Limit Dashboard (`GET /rate-limits/`, `frontend/src/mystic_auth/rate_limits/`) for viewing and resetting active limits
- [Downstream Integration Secrets](security/integration-secrets.md): provider boundary, external storage, rotation, and background-job handling rules
- [SECURITY.md](../../SECURITY.md): how to report a vulnerability privately (not via a public GitHub Issue)

---

## Error Monitoring

- [Error Monitoring](error-monitoring/overview.md): enabled-by-default backend/frontend error reporting via the Sentry SDK protocol; self-hosted Bugsink quickstart and what gets reported

---

## Geolocation

- [Session Geolocation](geolocation/overview.md): off-by-default IP-to-city/country resolution for Manage Sessions' Location column; MaxMind GeoLite2 account/license-key setup, Docker vs. non-Docker

---

## Appearance

- [Appearance: Per-User Brand Color](appearance/overview.md): per-account brand-color override on top of the app-wide default theme, live CSS custom-property rebuild, generated 50-900 color scale, favicon/meta sync, server reconciliation across devices

---

## Legal

- [Legal Documents and Signup Consent](legal/overview.md): the in-app Privacy Policy and Terms of Service pages, the signup consent notice (not a gating checkbox), and what an operator needs to edit before shipping to real users

---

## Translations

- [Translations Overview](translations/overview/README.md): supported languages (English, Hindi, Marathi, Gujarati) and mixed English-chrome modes, translation-store architecture
- [Tutorial: Adding a New Language](translations/adding-a-language.md): step-by-step walkthrough of adding a new language

---

## Testing

- [Testing Overview](testing/overview.md): backend pytest suites, frontend vitest suites, the CI coverage gate, and how to run
- [Manual Accessibility Checklist](testing/accessibility-manual-checklist.md): keyboard-only and screen-reader acceptance checks beyond axe automation

---

## Docker

- [Docker Overview](docker/overview.md): services, Dockerfiles, dev vs. prod compose, healthchecks
- [Docker Validation History](docker/validation-history.md): live-verification passes against the running stack, covering what was run, what it found, what got fixed

---

## CI/CD

- [CI/CD Overview](cicd/overview.md): GitHub Actions workflow, jobs, gaps

---

## Deployment

- [Deployment Guide](deployment/guide.md): mode chooser and links to focused deployment references
- [Environment and Runtime Configuration](deployment/environment.md): env file selection, build-time vs runtime settings, production review checklist
- [Frontend and Backend Routing](deployment/routing.md): same-origin nginx proxying, trusted proxy IPs, and SPA/API route collisions
- [Migrations and Backups](deployment/migrations-and-backups.md): Alembic service behavior, backup scripts, scheduled backup sidecar, restore discipline
- [Production Host Requirements](deployment/production-host.md): shutdown behavior, service responsibilities, host requirements, deployment limitations
- [Dev Deployment](deployment/dev.md): local development, hot reload, no TLS
- [Local-Prod Deployment](deployment/local-prod/README.md): self-hosted production image shape exposed via a free tunnel, no public server needed, with [Cloudflare Quick Tunnel](deployment/local-prod/cloudflare-quick-tunnel.md), [Cloudflare Named Tunnel](deployment/local-prod/cloudflare-named-tunnel.md), [ngrok](deployment/local-prod/ngrok-tunnel.md), and [Tailscale Funnel](deployment/local-prod/tailscale-funnel.md) walkthroughs
- [Prod Deployment](deployment/prod.md): self-hosted deployment on your own server with Caddy-managed TLS

---

## Concerns, Limitations & Technical Debt

- [Known Issues & Future Improvements](concerns/README.md): tracked limitations, technical debt, deferred security/performance work

---

## Project Story

- [Project Story](project-story/README.md): where this template came from and how its architecture settled into its current shape
- [How It Evolved](project-story/timeline/README.md): the commit-by-commit log, straight from the commit history
- [The Tools That Built It](project-story/tools.md): the workflows that actually did the work, from manual ChatGPT + VSCode through Claude Code and the first Codex pass

---

## Using This as a Template

- [Template Usage Guide](template-usage/overview.md): for anyone cloning this repo as a starting point for their own auth+PBAC project, an index into quickstart, the ownership split, building on the template, and deployment
- [Downstream Project Launch Checklist](template-usage/downstream-launch-checklist.md): project-specific legal, integration, VPS, recovery, monitoring, accessibility, and final acceptance work before serving real users
- [Quickstart](template-usage/quickstart.md): the one-command path from `git clone` to a working login, each step by hand instead, keeping env files honest over time, renaming the app, OAuth/email setup
- [Command Cheat Sheet](template-usage/cheatsheet.md): one-line "when to run this" for every script in the template, plus the `make` target shortcuts
- [The `app/` + `mystic_auth/` Split](template-usage/ownership-split.md): the file-ownership tiering table and diagram that keeps a `sync-upstream.sh` run low-conflict
- [Building On This Template](template-usage/customization.md): new domain/resource, database changes, adding permissions and protecting routes with PBAC, replacing the frontend
- [Frontend Customization](template-usage/frontend-customization.md): theme, pages, routing, state, and the shared-chrome extension points (nav items, navbar content, command palette search, audit log filters)
- [Worked Example: Adding a New Domain, End to End](template-usage/worked-example.md): a copy-and-rename starting point, covering model, schema, router, migration, policy, frontend page, route, and nav link, wired together for one fake domain
- [Staying in Sync with Upstream Template Updates](template-usage/syncing-upstream/README.md): pulling fixes/features from the original template into your own diverged project, step by step, plus a worked conflict-resolution example

---

## Who this is for

Anyone adding a new protected endpoint, a new permission, a new condition type, or a new policy to this template; anyone integrating a new frontend feature against the API; anyone debugging why an authorization decision or a request came back the way it did; or anyone new to the codebase who needs the system-wide picture before touching auth, authorization, or infrastructure code.

---

## Source of truth

This documentation describes the code as it exists in `backend/mystic_auth/` and `frontend/src/mystic_auth/` at the time of writing. If something here disagrees with the code, the code wins.

---
