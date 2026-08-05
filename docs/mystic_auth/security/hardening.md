# Security Hardening

Consolidates the concrete hardening mechanisms in the codebase: rate limiting, lockout, response headers, CORS, and cookie flags. For the *why* behind non-obvious choices, see [Security Decisions](decisions.md).

## Rate limiting

`backend/mystic_auth/auth/security/rate_limiter_service.py`: a generic sliding-window-by-fixed-bucket limiter backed by Redis (`INCR` + `EXPIRE` on first request in a window), applied via the `@rate_limiter_service.rate_limited("endpoint_name", account_key_func=...)` decorator on every route in `auth_routes.py` (signup, login, OAuth2 initiate/callback, `/auth/me`, logout, logout-all, password-reset request/confirm, verify-account). **Not** applied to `refresh_token_routes.py` (`POST /auth/refresh/`): that route relies instead on its own single-use-token rotation and reuse-detection protection (see [Security Decisions](decisions.md#rate-limiting-and-lockout-are-layered-not-singular)), which a generic request-volume limiter would only duplicate.

- **Always applies a per-IP limit** (`{endpoint_name}:ip:{ip}`), resolved via [`auth/security/client_ip.py`](../authorization/architecture.md#authorization-context-builder) (trusted-proxy-aware).
- **Optionally applies a per-account limit** when `account_key_func` is given (e.g. signup/password-reset-request key on the submitted email): closes the gap where an attacker spreads requests targeting one account across many source IPs to stay under the per-IP threshold alone.
- Both limits are configured by `MAX_REQUESTS_PER_WINDOW` / `REQUEST_WINDOW_SECONDS` (`.env.example`): one shared threshold/window for every rate-limited endpoint, not per-endpoint tunable today (see [Concerns](../concerns/README.md)).
- **Fails closed on Redis error, reviewed and kept intentionally**: `record_request` catches all exceptions, logs them, and returns `False` ("not allowed"): a Redis outage makes every rate-limited request appear over-limit and get rejected with `429`, rather than silently disabling rate limiting. This is the opposite tradeoff from the PBAC authorization cache, which fails open to the authoritative database on a Redis error: see [PBAC Troubleshooting: Redis cache management](../authorization/troubleshooting.md#redis-cache-management) for that contrast. Practical implication: a Redis outage makes the API fully unusable for any rate-limited auth route, not just slower: see [Security Decisions](decisions.md#rate-limiter-fails-closed-on-a-redis-outage--reviewed-kept-intentionally) for why this was kept rather than changed.

---

## Brute-force lockout

`backend/mystic_auth/auth/security/login_protection_service.py`: separate from and layered on top of the generic rate limiter (see [Security Decisions: rate limiting and lockout are layered](decisions.md#rate-limiting-and-lockout-are-layered-not-singular)):

- Per-account: `MAX_FAILED_LOGIN_ATTEMPTS` failures within `LOGIN_LOCKOUT_TIME` seconds locks that email out.
- Per-IP: `MAX_FAILED_LOGIN_ATTEMPTS_PER_IP` failures within `LOGIN_LOCKOUT_TIME_PER_IP` seconds locks that IP out across *any* account it targets.
- `check_and_record_action` double-checks `is_locked` both before and after the expensive password-hash comparison, closing a race where a concurrent request crosses the threshold mid-check.
- Both counters use `INCR`/`EXPIRE`-on-first-failure (not sliding), so the lockout window is fixed from the *first* failure, not extended by each subsequent one.

---

## Timing-attack resistance

See [Security Decisions: timing-attack mitigations](decisions.md#timing-attack-mitigations): applied at login (dummy-hash comparison), signup (unconditional hashing), and password-reset-request (identical generic response).

---

## Security response headers

`backend/mystic_auth/auth/security/security_headers_middleware.py`, applied to every response:

| Header | Value | Reasoning |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Stops MIME-type sniffing |
| `X-Frame-Options` | `DENY` | This is a JSON API with no HTML pages of its own beyond the auto-generated docs below: no framing use case exists |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` on every route except `/docs`/`/redoc`/`/openapi.json` (see below) | Zero functional cost on the real API surface since there's no HTML/script to allow |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (production only: see below) | Forces HTTPS for a year, protecting the cookies from protocol downgrade |
| `Referrer-Policy` | `no-referrer` | URLs here can carry sensitive query params (OAuth2 `state`/`code`) |

**HSTS is gated on `settings.ENVIRONMENT == "production"`** (checked fresh per request, not cached at import time). Sending it unconditionally would pin HSTS for a full year against real browser traffic even in a non-production deployment served over plain HTTP, with no way to turn it off short of a code change: browsers ignore the header over plain HTTP today, but that's not a reason to send a year-long pin somewhere it isn't intended to apply yet.

**`/docs`, `/redoc`, and `/openapi.json` get a relaxed CSP, carved out by request path.** FastAPI's auto-generated Swagger UI (`/docs`) and ReDoc (`/redoc`) pages: enabled whenever `ENVIRONMENT != "production"`, see `backend/app/main.py`: are the one place this API actually serves HTML, and both load their JS/CSS from a CDN (`cdn.jsdelivr.net`) plus an inline `<script>`/`<style>` block; ReDoc additionally pulls a Google Fonts stylesheet. The blanket `default-src 'none'` policy used to apply here too, which didn't error or warn: the page returned 200 and rendered as silently blank, every asset blocked with nothing in the response to say why. `security_headers_middleware.py`'s `_DOCS_PATHS`/`_DOCS_CSP` scope a permissive-but-specific policy (`cdn.jsdelivr.net`, `fonts.googleapis.com`/`fonts.gstatic.com`, `'unsafe-inline'`) to exactly those three paths; every other route keeps the strict policy above.

Note: no `Strict-Transport-Security` is set by the nginx layer serving the frontend static build (`docker/nginx.frontend.conf`): HSTS is only emitted by the backend API responses. See [Docker Overview](../docker/overview.md).

---

## CORS

`backend/app/main.py`: `CORSMiddleware` allows `settings.cors_allowed_origins` (`FRONTEND_BASE_URL` plus any comma-separated `FRONTEND_ADDITIONAL_BASE_URLS`; single-origin by default), `allow_credentials=True` (required for cookie-based auth to work cross-origin in dev, where frontend `:5173` and backend `:8000` are different origins), methods restricted to `GET/POST/PUT/PATCH/DELETE`, headers restricted to `Content-Type`. Redirect/email links (OAuth callback, verification, password reset) always point at `FRONTEND_BASE_URL` alone regardless of how many origins are CORS-allowed: there's always exactly one canonical link target.

---

## Cookies

| Cookie | Path | Flags | Set by |
|---|---|---|---|
| `access_token` | `/` | `httponly`, `secure`, `samesite=Strict` | `token_cookie_handler.py` |
| `refresh_token` | `/auth` | `httponly`, `secure`, `samesite=Strict` | `token_cookie_handler.py` |
| `oauth_state` | `/` | `httponly`, `secure`, `samesite=Lax` (must survive Google's cross-site redirect) | `oauth2_login_handler.py` |

`secure=True` on every cookie means **local HTTP development requires the browser to treat `localhost` as a secure context** (modern browsers do this automatically for `localhost`): this will not work over plain HTTP on a non-localhost hostname.

---

## Middleware ordering

`main.py` adds `CORSMiddleware`, `LoggingMiddleware`, `SecurityHeadersMiddleware`, then `CorrelationIdMiddleware` last: Starlette applies middleware in reverse of add order, so `CorrelationIdMiddleware` ends up outermost, ensuring `request.state.request_id` (and the logging contextvar it sets) is populated before any other middleware or route logic runs.

---

## Error handling

A single global exception handler (`main.py`) catches every otherwise-unhandled exception, logs it with a full traceback, and returns a generic `500 {"detail": "Internal Server Error"}`: internal exception details never reach the client, regardless of `ENVIRONMENT`; `debug=` is never passed to the FastAPI app either (defaults `False`), so there's no path where Starlette's own debug error page could leak a traceback. See [API Reference: error responses](../api/reference.md#error-responses). This same handler also reports the exception for error monitoring (`error_monitoring.sentry_service.capture_exception`): a no-op unless `SENTRY_DSN` is set, see [Error Monitoring](../error-monitoring/overview.md).

---

## Redis authentication

`REDIS_PASSWORD` (`.env`/`.env.example`) is passed to `redis-server --requirepass` in both compose files (empty value = no-op, so local dev is unaffected by default); both healthchecks authenticate with it. Since `redis-py` (`redis/client.py`) and `taskiq-redis` (`taskiq_tasks/email_tasks.py`) both authenticate via the connection URL rather than a separate kwarg, the same password must also be embedded in `REDIS_URL` (`redis://:<REDIS_PASSWORD>@redis:6379/0`): documented inline in `.env.example`.

---

## `SECRET_KEY` strength enforcement

`core/settings.py` rejects any `SECRET_KEY` under 32 characters at import time (`Settings._secret_key_minimum_strength`): a placeholder/example value fails fast at startup instead of silently signing tokens with weak entropy. This is a length floor, not a real entropy check (a 32-character low-entropy string still passes).

---

## Reverse-proxy IP trust

`auth/security/client_ip.py::get_client_ip` only trusts `X-Forwarded-For` when the literal TCP peer is listed in `TRUSTED_PROXY_IPS` (`.env`, empty/untrusted by default): every rate-limit, lockout, audit-log, and PBAC context call site goes through it. Deploying behind a reverse proxy only requires setting `TRUSTED_PROXY_IPS` to that proxy's address, no code change needed.

---

## Known accepted gaps

See [Concerns](../concerns/README.md) for the current open list (automated backup scheduling, the single global rate-limit threshold, no deploy automation): everything else previously tracked there has since been resolved and folded into this document. Error monitoring is available (opt-in) rather than a tracked gap now: see [Error Monitoring](../error-monitoring/overview.md).
