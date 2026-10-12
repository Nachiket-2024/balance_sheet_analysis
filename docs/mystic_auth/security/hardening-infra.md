# Security Hardening: Infrastructure
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Authentication Glossary](../glossary/authentication.md).*

Valkey authentication, secret strength, reverse-proxy IP trust, session geolocation, and the current accepted-gaps list. See [Security Hardening](hardening.md) for the full index.

---

## Valkey authentication

`VALKEY_PASSWORD` is required by every production and local-production Compose mode and is passed to `valkey-server --requirepass`; the Compose files fail before startup if it is missing. The development mode defaults email off but still receives a generated Valkey password from `setup-env`. Since `valkey-py` (`valkey/client.py`) authenticates through the connection URL rather than a separate kwarg, the same password is embedded in `VALKEY_URL` (`redis://:<VALKEY_PASSWORD>@valkey:6379/0`) by `setup-env`. (Background jobs no longer use Valkey at all: `procrastinate_tasks/` runs on the same Postgres instance as everything else, see [Background Email Delivery](../background-workers/procrastinate.md).)

---

## `SECRET_KEY` strength enforcement

`core/settings.py` rejects any `SECRET_KEY` under 32 characters at import time (`Settings._secret_key_minimum_strength`): a placeholder/example value fails fast at startup instead of silently signing tokens with weak entropy. This is a length floor, not a real entropy check (a 32-character low-entropy string still passes).

---

## Reverse-proxy IP trust

`auth/security/client_ip.py::get_client_ip` only trusts `X-Forwarded-For` when the literal TCP peer is listed in `TRUSTED_PROXY_IPS` (empty/untrusted by default): every rate-limit, lockout, audit-log, and PBAC context call site goes through it. Deploying behind a reverse proxy only requires setting `TRUSTED_PROXY_IPS` to that proxy's address, no code change needed. In the prod/local-prod-* Compose files, that value is derived automatically from `FRONTEND_STATIC_IP`/the tunnel's `*_STATIC_IP` var (see [Routing: Trusted proxy IPs](../deployment/routing.md#2-trusted-proxy-ips)) rather than set directly in `.env`. `Settings.TRUSTED_PROXY_IPS` defaults to `""` so it doesn't need to be present in the env file at all: only the `backend` service gets the derived value (via that Compose `environment:` override); `alembic` and `procrastinate_worker` read the same env file directly, never use this setting, and fall back to the default instead of failing to start.

---

## Session geolocation (Manage Sessions' Location column)

Resolves each login's city/country from its IP via a local MaxMind GeoLite2-City database, off by default. Split out into its own doc since it has a full setup flow (MaxMind account, license key, Docker profile) rather than being a simple config flag: see [Session Geolocation](../geolocation/overview.md).

---

## Known accepted gaps

1. See [Concerns](../concerns/README.md) for the current open list (off-host backup shipping, no deploy automation): everything else previously tracked there, including automated backup scheduling and the single global rate-limit threshold, has since been resolved and folded into this document.
2. `pytest` no longer ships in the production backend image: `docker/mystic_auth/dockerfiles/backend.Dockerfile`'s multi-stage build has a `runtime` target (no test tooling, the default and the only target `backend`/`procrastinate_worker`/`alembic` actually run) and a separate `test` target that layers `requirements-dev.txt` on top of it, selected via the backend service's `target: ${BACKEND_BUILD_TARGET:-runtime}` in `docker-compose.dev.yml`.
3. Error monitoring is available (opt-in) rather than a tracked gap now: see [Error Monitoring](../error-monitoring/overview.md).

---
