# Security Decisions
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Authentication Glossary](../glossary/authentication.md).*

A decision log capturing the *why* behind non-obvious security choices in this codebase, gathered in one place instead of scattered across code comments. Each entry links to where the actual implementation lives. Split by category into three pages, indexed below.

---

## Auth & session

See [Security Decisions: Auth & Session](decisions-auth.md) for the full entries.

- [Role is never used to decide access](decisions-auth.md#role-is-never-used-to-decide-access): PBAC, not role-based access control - `users.role` is display metadata only.
- [Why current-user lookups re-query the database every time](decisions-auth.md#why-current-user-lookups-re-query-the-database-every-time): makes deactivation take effect on the next request, not at token expiry.
- [Email addresses are normalized, case-insensitively, everywhere](decisions-auth.md#email-addresses-are-normalized-case-insensitively-everywhere): normalized at lookup, insert, and every input boundary.
- [Timing-attack mitigations](decisions-auth.md#timing-attack-mitigations): login, signup, and password-reset request are all enumeration-resistant.
- [Token replay and reuse detection](decisions-auth.md#token-replay-and-reuse-detection): single-use refresh tokens, chain-scoped revocation on reuse, atomic rotation.
- [Revocation is version-based](decisions-auth.md#revocation-is-version-based-one-durable-postgres-version-bump-not-a-token-registry-to-iterate): one durable Postgres increment, not a registry to iterate.
- [OAuth2 CSRF and account-hijacking protections](decisions-auth.md#oauth2-csrf-and-account-hijacking-protections): state + PKCE, `email_verified`, pre-registration hijack handling, fixed redirect URI.
- [The signup/OAuth2 email race](decisions-auth.md#the-signupoauth2-email-race): closed by a DB unique constraint, not application-level locking.
- [Self-service password change requires the current password](decisions-auth.md#self-service-password-change-requires-the-current-password): prevents a hijacked session cookie from locking out the real owner.
- [Logout and logout-all are idempotent](decisions-auth.md#logout-and-logout-all-are-idempotent-about-an-already-dead-refresh-token): about an already-dead refresh token.
- [Rate limiting and lockout are layered, not singular](decisions-auth.md#rate-limiting-and-lockout-are-layered-not-singular): generic rate limiting plus a purpose-built brute-force lockout, including why the rate limiter fails closed on a Valkey outage.

---

## Infrastructure

See [Security Decisions: Infrastructure](decisions-infra.md) for the full entries.

- [`.dockerignore` previously let local files leak into built images](decisions-infra.md#dockerignore-previously-let-local-files-leak-into-built-images): two real, verified image-content leaks, both fixed.
- [`Settings` ignores env vars it doesn't declare](decisions-infra.md#settings-ignores-env-vars-it-doesnt-declare-because-env-is-shared-with-docker-compose): because `.env` is shared with Docker Compose.
- [A malformed `SENTRY_DSN` must never crash the app](decisions-infra.md#a-malformed-sentry_dsn-must-never-crash-the-app): `init_sentry()` fails soft, monitoring-only.
- [Background task queue: Taskiq vs Celery](decisions-infra.md#background-task-queue-taskiq-vs-celery): the original reasoning, kept as historical record.
- [Taskiq replaced with Procrastinate](decisions-infra.md#taskiq-replaced-with-procrastinate): a full swap to a Postgres-native queue, and why.
- [Least-privilege app DB role instead of running as Postgres superuser](decisions-infra.md#least-privilege-app-db-role-instead-of-running-as-postgres-superuser): what it protects against, what it doesn't, and why not Row-Level Security.
- [Test suite gets its own dedicated Postgres database](decisions-infra.md#test-suite-gets-its-own-dedicated-postgres-database): a real dev-stack procrastinate_worker crash, traced to tests deleting jobs out from under it.

---

## Product decisions

See [Security Decisions: Product](decisions-product.md) for the full entries.

- [Account lifecycle: soft delete by default](decisions-product.md#account-lifecycle-soft-delete-by-default): reversible by default, purge gated by its own permission, grace-period auto-purge.
- [Why MFA is not enabled](decisions-product.md#why-mfa-is-not-enabled): an intentionally deferred scope boundary, with the hooks already in place.
- [Intentionally deferred features](decisions-product.md#intentionally-deferred-features): non-SMTP email providers, deploy automation. See [Known Issues](../concerns/README.md) for the current backlog of accepted gaps and follow-ups.

---
