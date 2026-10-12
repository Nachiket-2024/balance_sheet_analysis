# Security Hardening
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Authentication Glossary](../glossary/authentication.md).*

Consolidates the concrete hardening mechanisms in the codebase: rate limiting, lockout, response headers, CORS, and cookie flags. For the *why* behind non-obvious choices, see [Security Decisions](decisions.md). Split by category into three pages, indexed below.

---

## Abuse prevention

See [Security Hardening: Abuse Prevention](hardening-abuse-prevention.md) for the full entries.

- [Rate limiting](hardening-abuse-prevention.md#rate-limiting): generic per-IP/per-account limiter, fails closed on Valkey error, the Rate Limit Dashboard.
- [Brute-force lockout](hardening-abuse-prevention.md#brute-force-lockout): per-account and per-IP failed-login lockout, layered on top of rate limiting.
- [Timing-attack resistance](hardening-abuse-prevention.md#timing-attack-resistance): dummy-hash comparison, unconditional hashing, identical generic responses.

---

## HTTP layer

See [Security Hardening: HTTP Layer](hardening-http.md) for the full entries.

- [Security response headers](hardening-http.md#security-response-headers): `X-Content-Type-Options`, `X-Frame-Options`, CSP, HSTS, `Referrer-Policy`, `Permissions-Policy`.
- [CORS](hardening-http.md#cors): allowed origins, credentials, methods, headers.
- [Cookies](hardening-http.md#cookies): `access_token`/`refresh_token`/`oauth_state` paths and flags.
- [Middleware ordering](hardening-http.md#middleware-ordering): why `CorrelationIdMiddleware` ends up outermost.
- [Error handling](hardening-http.md#error-handling): the global exception handler and `AppError`'s structured error responses.

---

## Infrastructure

See [Security Hardening: Infrastructure](hardening-infra.md) for the full entries.

- [Valkey authentication](hardening-infra.md#valkey-authentication): `VALKEY_PASSWORD`, embedded in `VALKEY_URL`.
- [`SECRET_KEY` strength enforcement](hardening-infra.md#secret_key-strength-enforcement): rejects weak keys under 32 characters at import time.
- [Reverse-proxy IP trust](hardening-infra.md#reverse-proxy-ip-trust): `TRUSTED_PROXY_IPS` gates `X-Forwarded-For` trust.
- [Session geolocation](hardening-infra.md#session-geolocation-manage-sessions-location-column): MaxMind GeoLite2-City, off by default.
- [Known accepted gaps](hardening-infra.md#known-accepted-gaps): see [Concerns](../concerns/README.md) for the current open list.

---
