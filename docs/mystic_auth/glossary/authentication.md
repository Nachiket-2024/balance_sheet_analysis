# Glossary: Authentication & Sessions
---

Tokens, cookies, login defenses, and account lifecycle terms. See [Glossary](README.md) for the full index.

---

## JWT

Short for JSON Web Token. A signed, tamper-evident string that carries a small set of claims (facts) about who a session belongs to and when it expires. This app issues two per login: an access token and a refresh token. See [Authentication Overview: Tokens and cookies](../authentication/overview.md#tokens-and-cookies).

---

## claim

One field inside a JWT's payload, such as `email`, `type`, `exp` (expiry), or `chain` (see [chain / chain_id](#chain--chain_id) below). A claim is only as trustworthy as the token's signature; this app deliberately keeps sensitive facts like `role` out of claims and re-checks them against the database instead. See [Authentication Overview: Tokens and cookies](../authentication/overview.md#tokens-and-cookies).

---

## httpOnly cookie

A cookie flagged so that JavaScript in the browser can never read it, only the browser itself sends it back on requests. Both the `access_token` and `refresh_token` cookies use this, which is why a successful XSS attack still can't steal a session token out of them. See [Authentication Overview: Tokens and cookies](../authentication/overview.md#tokens-and-cookies).

---

## SameSite

A cookie attribute that limits when a browser attaches a cookie to a cross-site request. This app uses `Strict` for `access_token`/`refresh_token` (never sent cross-site at all) and `Lax` for the OAuth2 `oauth_state` cookie, which needs to survive Google's own cross-site redirect back to the callback. See [OAuth2 / PKCE: CSRF protection](../authentication/oauth2-pkce.md#csrf-protection-state).

---

## refresh-token rotation

Every time the app mints a new access token from a refresh token, it also issues a brand-new refresh token and retires the old one. A retired refresh token can never be redeemed again; if it is presented a second time, that's treated as a sign of theft or replay, not a normal retry. See [Authentication Overview: Refresh token rotation](../authentication/overview.md#refresh-token-rotation).

---

## chain / chain_id

A random id minted once at login and carried forward unchanged through every rotation of that one login session. It's what a targeted "end this session" action actually revokes, and what tells apart "this device's session" from "every session on the account." See [Session Management: Source of truth](../authentication/session-management/README.md#source-of-truth).

---

## PKCE

Short for Proof Key for Code Exchange (pronounced "pixy"). An OAuth2 extension that stops a stolen authorization code from being redeemed by anyone but the party that started the login. This app's Google login generates a random secret, sends only a hash of it to Google upfront, then proves possession of the original secret when exchanging the code for tokens. See [OAuth2 / PKCE](../authentication/oauth2-pkce.md#pkce-mechanics).

---

## CSRF

Short for Cross-Site Request Forgery: an attack where a malicious site tricks a logged-in user's browser into making a request it didn't intend. The OAuth2 login flow defends against a CSRF variant (a forged callback) using a one-time `state` value checked against both a cookie and a server-side record. See [OAuth2 / PKCE: CSRF protection](../authentication/oauth2-pkce.md#csrf-protection-state).

---

## OAuth 2.0

An authorization protocol that lets an application use a provider's login or
data-access decision without receiving the user's provider password. In this
app, Google authenticates the user and MysticAuth then creates its own session;
the app does not store a Google refresh token. See [OAuth2 / PKCE](../authentication/oauth2-pkce.md).

---

## OIDC (OpenID Connect)

An identity layer built on OAuth 2.0. The `openid` scope tells Google that the
flow is being used for sign-in and identity, not only delegated API access.

---

## redirect URI

The exact URL to which an OAuth provider sends the browser after consent. The
provider compares it with the registered value, so scheme, hostname, path, and
trailing slash must match exactly. This app uses `GOOGLE_REDIRECT_URI` on the
backend.

---

## OAuth consent screen

The provider page that identifies the application and shows the requested
scopes before the user approves login. Google manages its publishing, test-user,
branding, and verification status in Google Cloud Console.

---

## superuser (system account)

A single reserved account (`role == system`) with full access, created only via a one-off script, never through the API or a self-service signup. It's blocked from Google OAuth2 login entirely and can only authenticate with a password. See [System Superuser: Bootstrapping and Promotion](../authentication/system-superuser/README.md).

---

## soft delete

Marking a row as deleted (setting a `deleted_at` timestamp) instead of actually removing it from the database. A soft-deleted account can still be inspected or reactivated by a caller with the required permission during its grace period, unlike a hard delete (purge), which is irreversible. See [Account Deletion and Purge](../authentication/account-deletion/README.md) and [Database Design](../database/design.md).

---

## grace period

The window of time after a soft delete during which an account can still be reactivated before the scheduled background job permanently purges it. See [Account Deletion and Purge](../authentication/account-deletion/README.md).

---

## idempotency

A property of an operation where doing it more than once has the same effect as doing it once. Logout is idempotent: calling it on an already-ended session doesn't error, it just confirms the session is gone. See [Logout and Logout-All](../authentication/logout.md).

---

## timing-attack resistance

Making sure a request takes roughly the same amount of time whether it succeeds or fails, so an attacker can't infer something secret (like "does this email exist") purely from how fast the server responded. Login intentionally does constant-effort work on both the found-user and no-such-user paths. See [Login](../authentication/login.md).

---

## brute-force lockout

A defense that locks out an account or IP address after too many failed login attempts within a time window, separate from and layered on top of the generic rate limiter below. See [Security Hardening: Brute-force lockout](../security/hardening-abuse-prevention.md#brute-force-lockout).

---

## rate limiting

A defense that caps how many requests a single IP address or account can make to a given endpoint within a time window, to blunt brute-force and scripted abuse. It's separate from brute-force lockout (which specifically targets repeated failed logins on one account). See [Security Hardening: Rate limiting](../security/hardening-abuse-prevention.md#rate-limiting).

---

## Argon2

The password-hashing algorithm this app uses to store passwords (never the plain password itself). It's deliberately slow, which is what makes guessing a password by brute force expensive even if the password hashes are ever stolen. See [Security Hardening: Brute-force lockout](../security/hardening-abuse-prevention.md#brute-force-lockout).

---

## SSE (Server-Sent Events)

A one-way, long-lived HTTP connection the server uses to push events to the browser without the browser having to poll. This app uses it for `GET /auth/session-events`, so an open tab learns about a revoke, a new login, or a permissions change within milliseconds. See [Session Management: Real-time push](../authentication/session-management/real-time-push.md#real-time-push).

---

## consent (signup)

The notice shown at signup stating that continuing means agreeing to the Terms of Service and Privacy Policy. It's informational text, not a gating checkbox the user must tick before they can submit the form. See [Legal Documents and Signup Consent](../legal/overview.md).

---

## verification token

A one-time token emailed to a new account at signup, redeemed via `POST /auth/verify-account` to mark the account `is_verified=True`. A separate "resend" endpoint reissues one if the original expires or gets lost. See [Signup and Email Verification](../authentication/signup-and-verification.md).

---

## reactivate

Restoring a soft-deleted or deactivated account back to normal, either by a caller with the required permission (for a soft-deleted account still inside its grace period) or by the same account holder in some flows. Distinct from a purge, which is permanent and cannot be undone. See [Account Deletion and Purge](../authentication/account-deletion/README.md).

---

## purge

The irreversible hard delete of an account and its data from the database, run either by a caller with the required permission or by the scheduled background job once a soft-deleted account's grace period has passed. See [Account Deletion and Purge](../authentication/account-deletion/README.md).

---

## jti

Short for JWT ID: a unique identifier embedded in every refresh token, used to enforce that each one can be redeemed exactly once (`claim_jti_for_rotation`, a unique Postgres claim in `consumed_refresh_tokens`). Two requests racing to redeem the same refresh token can never both win. See [Authentication Overview: Refresh token rotation](../authentication/overview.md#refresh-token-rotation).

---

## token revocation

Ending a session's validity before its JWT would naturally expire. This app does it by version, not by blacklist: bumping a durable Postgres version (`account_ver` or `chain_ver`) instantly invalidates every token that embedded an older version, with nothing to look up per token. See [Session Management: Source of truth](../authentication/session-management/README.md#source-of-truth).

---

## XSS (Cross-Site Scripting)

An attack where malicious JavaScript gets injected into and runs on a page, potentially able to read anything ordinary page JavaScript can. This app's httpOnly cookies (see above) mean even a successful XSS can't read out the session tokens directly.

---
