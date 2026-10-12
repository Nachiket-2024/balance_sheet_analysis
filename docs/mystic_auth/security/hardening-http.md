# Security Hardening: HTTP Layer
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Authentication Glossary](../glossary/authentication.md).*

Response headers, CORS, cookie flags, middleware ordering, and error handling: the mechanisms that shape what the HTTP layer itself exposes to a client. See [Security Hardening](hardening.md) for the full index.

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
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=()` | This is a JSON API with no page of its own that would ever invoke these browser features: denying them closes off a class of clickjacking-adjacent abuse at zero functional cost |
| `Cross-Origin-Opener-Policy` | `same-origin` | No legitimate cross-origin window needs to reference this one |
| `Cross-Origin-Resource-Policy` | `same-origin` | Blocks cross-origin scripts from reading these responses (Spectre-style side channels) |
| `Cross-Origin-Embedder-Policy` | `require-corp` (skipped on `/docs` and the other doc paths, since jsdelivr/Google Fonts don't opt in via CORP/CORS) | Same rationale as COOP/CORP above |

1. **HSTS is gated on `settings.ENVIRONMENT == "production"`** (checked fresh per request, not cached at import time). Sending it unconditionally would pin HSTS for a full year against real browser traffic even in a non-production deployment served over plain HTTP, with no way to turn it off short of a code change: browsers ignore the header over plain HTTP today, but that's not a reason to send a year-long pin somewhere it isn't intended to apply yet.

2. **`/docs`, `/redoc`, and `/openapi.json` get a relaxed CSP, carved out by request path.**
   - FastAPI's auto-generated Swagger UI (`/docs`) and ReDoc (`/redoc`) pages are enabled whenever `ENVIRONMENT != "production"` (see `backend/app/main.py`), and are the one place this API actually serves HTML.
   - Both load their JS/CSS from a CDN (`cdn.jsdelivr.net`) plus an inline `<script>`/`<style>` block; ReDoc additionally pulls a Google Fonts stylesheet.
   - The blanket `default-src 'none'` policy used to apply here too, and it didn't error or warn: the page returned 200 and rendered as silently blank, every asset blocked with nothing in the response to say why.
   - `security_headers_middleware.py`'s `_DOCS_PATHS`/`_DOCS_CSP` scope a permissive-but-specific policy (`cdn.jsdelivr.net`, `fonts.googleapis.com`/`fonts.gstatic.com`, `'unsafe-inline'`) to exactly those three paths; every other route keeps the strict policy above.

3. `Strict-Transport-Security` on the frontend static build is set by nginx itself (`docker/mystic_auth/nginx.frontend.conf`), unconditionally rather than gated on `ENVIRONMENT` like the backend's copy: the frontend production image only ever ships in a production-shaped deployment, and needs to send it itself since the local-prod-ngrok/cloudflare/tailscale tunnel modes have no other layer in front of it that would. `docker/mystic_auth/Caddyfile` (the real prod TLS terminator) deliberately does *not* also set it: nginx already covers every response reaching Caddy, backend and frontend alike, so Caddy adding it too would just duplicate the header. See [Docker Overview](../docker/overview.md).

4. `docker/mystic_auth/nginx.frontend.conf` mirrors most of the backend's header set for the SPA response (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, `Cross-Origin-Embedder-Policy`, plus its own less-strict CSP), and also disables `server_tokens` to stop the nginx version leaking in the `Server` response header.

5. The frontend's `style-src` and `script-src` have no `'unsafe-inline'`. The one `style-src` hash and the one `script-src` hash are both confirmed against the current build: they cover `frontend/index.html`'s pre-React boot shell, a `<style>` block for its layout/colors and a small synchronous `<script>` that sets its dark/light mode from `localStorage` before paint. Confirmed live by removing every other hash and sweeping every route (all authenticated and public pages, all 7 language modes, including the dashboard chart's hover tooltip) with a `securitypolicyviolation` listener armed: zero violations, so nothing else in the current build needs an inline-style/script allowance. A real CSP violation on exactly this boot-shell `<style>` block was found and fixed live in an earlier pass (the browser silently drops a disallowed inline style or script, so the failure mode is a rendering bug, not a console error a casual check would catch) - do not assume "the page rendered fine" during any check meant the CSP was actually satisfied; check the browser console for `securitypolicyviolation`/CSP messages directly. A separate, unrelated violation was later found and fixed the same way: three of the app's own components injected runtime `<style>` tags via React's `<style href precedence>` resource-hoisting API, which a hash-only CSP can never allow since their content has no fixed hash to add ahead of time - moved into the real stylesheet (`theme/tailwind.css`) instead, the only fix that works under this CSP. See the comment above `style-src`/`script-src` in `docker/mystic_auth/nginx.frontend.conf` for exactly what each hash covers and how to regenerate it.

6. The shared frontend toast renderer (`frontend/src/mystic_auth/ui/toaster/`) is template-owned and styled from the bundled Tailwind stylesheet. It deliberately does not use a library that injects runtime `<style>` tags, so toast notifications remain compatible with the strict production CSP without adding `'unsafe-inline'`. Downstream projects should use the exposed toaster/components from `frontend/src/app/sdk.ts`; changes to shared toast styling belong in an upstream contribution, not in `frontend/src/mystic_auth/theme/tailwind.css`.

---

## CORS

`backend/app/main.py`: `CORSMiddleware` is configured as follows.

1. **Allowed origins**: `settings.cors_allowed_origins` (`FRONTEND_BASE_URL` plus any comma-separated `FRONTEND_ADDITIONAL_BASE_URLS`; single-origin by default).
2. **Credentials**: `allow_credentials=True`, required for cookie-based auth to work cross-origin in dev, where frontend `:5173` and backend `:8000` are different origins.
3. **Methods**: restricted to `GET/POST/PUT/PATCH/DELETE`.
4. **Headers**: restricted to `Content-Type`.
5. Redirect/email links (OAuth callback, verification, password reset) always point at `FRONTEND_BASE_URL` alone regardless of how many origins are CORS-allowed: there's always exactly one canonical link target.

---

## Cookies

| Cookie | Path | Flags | Set by |
|---|---|---|---|
| `access_token` | `/` | `httponly`, `secure` outside development, `samesite=Strict` | `token_cookie_handler.py` |
| `refresh_token` | `/auth` | `httponly`, `secure` outside development, `samesite=Strict` | `token_cookie_handler.py` |
| `oauth_state` | `/` | `httponly`, `secure` outside development, `samesite=Lax` (must survive Google's cross-site redirect) | `oauth2_login_handler.py` |

The development stack uses plain HTTP, so it intentionally omits `Secure` for browser
compatibility. Local-prod and production must use HTTPS and set `Secure`; the setting is
derived from `ENVIRONMENT`, not from a request-controlled host or scheme.

---

## Middleware ordering

1. `main.py` adds middleware in this order: `CORSMiddleware`, `LoggingMiddleware`, `SecurityHeadersMiddleware`, then `CorrelationIdMiddleware` last.
2. Starlette applies middleware in reverse of add order, so `CorrelationIdMiddleware` ends up outermost.
3. This ensures `request.state.request_id` (and the logging contextvar it sets) is populated before any other middleware or route logic runs.

---

## Error handling

Two handlers registered in `main.py`:

1. **Global `@app.exception_handler(Exception)`**: catches every otherwise-unhandled exception, logs it with a full traceback, and returns a generic `500 {"detail": "Internal Server Error"}`.
   - Internal exception details never reach the client, regardless of `ENVIRONMENT`; `debug=` is never passed to the FastAPI app either (defaults `False`), so there's no path where Starlette's own debug error page could leak a traceback.
   - This same handler also reports the exception for error monitoring (`error_monitoring.sentry_service.capture_exception`): a no-op unless `SENTRY_DSN` is set. See [Error Monitoring](../error-monitoring/overview.md).

2. **More specific `@app.exception_handler(AppError)`**: catches `core/errors.py`'s `AppError`, the structured exception routes raise on purpose (`AppError(status_code, code, detail, params=None)`), and returns `{"detail", "code", "params"}` instead of the generic body above.
   - `code` is a stable, machine-readable identifier (e.g. `"INVALID_CREDENTIALS"`).
   - The frontend's `api/apiError.ts` looks it up in `errors.json` to render a translated message, falling back to the English `detail` for any route not yet migrated to `AppError`.
   - See [API Reference: error responses](../api/reference.md#error-responses) and [Translations Overview](../translations/overview/ui-and-errors.md#5-backend-error-codes-frontendsrcmystic_authapiapierrorts).

---
