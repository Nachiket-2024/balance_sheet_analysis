# Documentation

Documentation for this full-stack template, organized by feature/domain to mirror the actual code layout (`backend/mystic_auth/<domain>/`, `frontend/src/mystic_auth/<domain>/`). If something here disagrees with the code, the code wins, so file an issue or update the doc.

This is the template's own reference documentation, belonging to upstream and not yours to edit. Your own project's docs go in [`docs/app/`](../app/README.md) instead, so they never conflict with a future `scripts/upstream-sync/sync-upstream.sh` run. See [Using This Repository as a Template: the `app/` + `mystic_auth/` split](template-usage/overview.md#the-app--mystic_auth-split) for the full reasoning.

## Architecture

- [System Overview](architecture/system-overview.md): whole-stack component diagram, why the stack is split this way, request lifecycle
- [Backend Architecture](architecture/backend.md): `backend/mystic_auth/` module layout, request pipeline, middleware
- [Frontend Architecture](architecture/frontend.md): `frontend/src/mystic_auth/` module layout, state management, routing, theming

---

## Authentication

- [Authentication Overview](authentication/overview.md): signup, verification, login, refresh/logout, password reset, JWT/cookie mechanics
- [Session Management](authentication/session-management.md): active-session tracking, refresh-token rotation mirror, dashboard card behavior, revoke edge cases
- [OAuth2 / PKCE](authentication/oauth2-pkce.md): Google OAuth2 login flow, PKCE code-challenge mechanics, CSRF state protection
- [System Superuser: Bootstrapping and Promotion](authentication/system-superuser.md): `create_system_user.py`'s full behavior, covering fresh creation, promoting an existing account, and the Google-only-account special case

---

## Authorization (PBAC)

- [Architecture Overview](authorization/architecture.md): request flow, component responsibilities, integration points
- [Policy JSON Examples](authorization/policy-examples.md): basic, conditioned, superuser, and self-service policies
- [RBAC Quickstart](authorization/rbac-quickstart.md): plain role-shaped access (no conditions) using the same policies, for projects that don't need PBAC's full generality
- [Common Patterns](authorization/common-patterns.md): modeling common access shapes (e.g. org-chart/company-group hierarchies) on top of PBAC's existing condition types
- [Condition Schema Reference](authorization/condition-schema-reference.md): every supported condition type, field-by-field
- [Adding New Permissions](authorization/adding-permissions.md): extending the action vocabulary
- [Adding New Condition Handlers](authorization/adding-condition-handlers.md): extending the condition framework
- [Writing and Testing Policies](authorization/writing-testing-policies.md): policy lifecycle, local testing, unit test patterns
- [Operational Troubleshooting Guide](authorization/troubleshooting.md): common issues, logging, Redis/DB debugging

---

## Database

- [Database Design](database/design.md): schema, foreign keys, account lifecycle (soft delete/purge/reactivate)

---

## API

- [API Reference](api/reference.md): route inventory grouped by domain, request/response shapes, auth requirements

---

## Background Email Delivery

- [Background Email Delivery](background-workers/taskiq.md): Taskiq worker setup, Redis broker behavior, failure handling

---

## Security

- [Security Decisions](security/decisions.md): the *why* behind non-obvious security choices, plus known accepted gaps
- [Security Hardening](security/hardening.md): rate limiting, lockout, security headers, CORS, cookie flags, consolidated
- [SECURITY.md](../../SECURITY.md): how to report a vulnerability privately (not via a public GitHub Issue)

---

## Error Monitoring

- [Error Monitoring](error-monitoring/overview.md): enabled-by-default backend/frontend error reporting via the Sentry SDK protocol; self-hosted Bugsink quickstart and what gets reported

---

## Testing

- [Testing Overview](testing/overview.md): backend pytest suites, frontend vitest suites, coverage state, how to run

---

## Docker

- [Docker Overview](docker/overview.md): services, Dockerfiles, dev vs. prod compose, healthchecks
- [Docker Validation History](docker/validation-history.md): live-verification passes against the running stack, covering what was run, what it found, what got fixed

---

## CI/CD

- [CI/CD Overview](cicd/overview.md): GitHub Actions workflow, jobs, gaps

---

## Deployment

- [Deployment Guide](deployment/guide.md): shared reference, environment variables, migrations, backups, host requirements
- [Dev Deployment](deployment/dev.md): local development, hot reload, no TLS
- [Local-Prod Deployment](deployment/local-prod.md): self-hosted production image shape exposed via a free Cloudflare Tunnel, no public server needed
- [Prod Deployment](deployment/prod.md): self-hosted deployment on your own server with Caddy-managed TLS

---

## Concerns, Limitations & Technical Debt

- [Known Issues & Future Improvements](concerns/README.md): tracked limitations, technical debt, deferred security/performance work

---

## Project Story

- [Project Story](project-story/README.md): where this template came from and how it evolved, straight from the commit history
- [The Tools That Built It](project-story/tools.md): the workflows that actually did the work, from manual ChatGPT + VSCode through Claude Code and the first Codex pass

---

## Using This as a Template

- [Template Usage Guide](template-usage/overview.md): for anyone cloning this repo as a starting point for their own auth+PBAC project, covering quickstart, environment configuration, renaming the app, frontend/backend customization, OAuth/email setup, adding permissions and protecting routes, replacing the frontend, deployment
- [Worked Example: Adding a New Domain, End to End](template-usage/worked-example.md): a copy-and-rename starting point, covering model, schema, router, migration, policy, frontend page, route, and nav link, wired together for one fake domain
- [Staying in Sync with Upstream Template Updates](template-usage/syncing-upstream.md): pulling fixes/features from the original template into your own diverged project, step by step, plus a worked conflict-resolution example

---

## Who this is for

Anyone adding a new protected endpoint, a new permission, a new condition type, or a new policy to this template; anyone integrating a new frontend feature against the API; anyone debugging why an authorization decision or a request came back the way it did; or anyone new to the codebase who needs the system-wide picture before touching auth, authorization, or infrastructure code.

---

## Source of truth

This documentation describes the code as it exists in `backend/mystic_auth/` and `frontend/src/mystic_auth/` at the time of writing. If something here disagrees with the code, the code wins.
