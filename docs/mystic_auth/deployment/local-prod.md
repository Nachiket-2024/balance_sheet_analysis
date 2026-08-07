# Local-Prod Deployment

Self-hosted production image/runtime shape from your own machine or home
server. The code is baked into images, reload is off, bind mounts are gone,
and Cloudflare Tunnel exposes the app to the internet without your own public
IP, router port forwarding, or Caddy.

Not sure this is the mode you want? See the
[dev vs. local-prod vs. prod comparison](guide.md#at-a-glance) in the
Deployment Guide.

---

## Getting started

This gets your self-hosted stack live on the internet with zero Cloudflare
account or domain setup, using the default Quick Tunnel mode.

**Step 1: Copy the env file.**

```bash
cp .env.local-prod.example .env
```

`.env.local-prod.example` is the local-prod template for
`docker-compose.local-prod.yml`. It is preconfigured for Quick Tunnel:
`VITE_API_BASE_URL` is empty for same-origin API calls, and
`TRUSTED_PROXY_IPS=172.28.0.10` matches the fixed frontend nginx address.
You can boot before filling in Google or SMTP credentials. The CLI-created
system superuser can still sign in and view the dashboard because the script
marks it verified. Regular users need one verification path: SMTP for password
signup, email verification, and password reset, or Google OAuth2 login.

Do not start local-prod from `.env.example`. That file points the frontend at
localhost dev ports and leaves production routing values unset. See
[Choosing the right env template](guide.md#choosing-the-right-env-template)
for the mode comparison.

---

**Step 2: Start the stack.**

```bash
docker compose -f docker-compose.local-prod.yml up -d --build
```

---

**Step 3: Get your public URL.**

```bash
docker compose -f docker-compose.local-prod.yml logs -f cloudflared
```

Within a few seconds, this prints a `https://<random-words>.trycloudflare.com`
URL: that's your app, live on the internet. Open it in a browser.

`frontend` (port 80) and `backend` (port 8000) are also published to the
host for local debugging, but the public entrypoint is `cloudflared`, not
those ports.

Read on for what this mode does and doesn't cover, and how to upgrade to
a stable domain.

---

## Cloudflare Tunnel: two modes

Controlled by `docker-compose.local-prod.yml`'s `cloudflared` service
`command:`, and by whether `TUNNEL_TOKEN` is set in `.env`.

### Quick Tunnel (default, zero setup)

```yaml
command: tunnel --no-autoupdate --url http://frontend:80
```

No Cloudflare account, no domain. `cloudflared`'s logs print a fresh
`https://<random-words>.trycloudflare.com` URL every time the container
starts. Good for testing. The URL changes on every restart, so don't rely
on it as a stable, shareable link.

#### Do I need to update `FRONTEND_BASE_URL`/`BACKEND_BASE_URL`?

**For password login and browsing, no.** This is already handled for you:
`VITE_API_BASE_URL` is left empty in `.env.local-prod.example`, so the
frontend calls the API on the same origin it was loaded from, whatever the
current tunnel URL is, and nginx proxies that same-origin request to
`backend` internally. Nothing needs to track the tunnel URL for signup,
password login, or browsing to work.

**For Google login, yes: `FRONTEND_BASE_URL` must track the tunnel URL.**
Unlike every other flow, the OAuth2 callback (`oauth2_login_handler.py`)
issues a hard, cross-origin redirect built from `FRONTEND_BASE_URL` after
setting the auth cookies on the tunnel host. If `FRONTEND_BASE_URL` is
stale (e.g. left at `http://localhost`), the browser gets sent to a
different origin than the one holding the cookies, `/auth/me` comes back
401, and the user is bounced to `/login`, even though the account was
created/verified successfully server-side. Keep it in sync with
`GOOGLE_REDIRECT_URI` below.

- `FRONTEND_BASE_URL`: also baked into verification/password-reset email
  links and the CORS allow-list. A stale value breaks Google login (above)
  and points emailed links at the wrong URL.
- `BACKEND_BASE_URL`: must be *set* for the app to boot (it's a required
  setting), but nothing in the app currently reads it at runtime. It never
  needs to track the tunnel URL.

Two things need updating in step with a changing Quick Tunnel URL:
`FRONTEND_BASE_URL` (for Google login to redirect back to the right
origin) and `GOOGLE_REDIRECT_URI` (for Google to accept the callback) when
Google login is enabled:

#### Updating for a new Quick Tunnel URL

Do this after every restart when Google login should work through the public
URL for that session:

**Step 1:** Get the new URL from the logs:

```bash
docker compose -f docker-compose.local-prod.yml logs cloudflared | grep trycloudflare.com
```

---

**Step 2:** In the [Google Cloud Console](https://console.cloud.google.com/),
under **APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`<new URL>/auth/oauth2/callback/google` under **Authorized redirect URIs**
and `<new URL>` under **Authorized JavaScript origins**. Old entries from
past restarts can be removed, or left there. Google allows multiple.

---

**Step 3:** In `.env`, update:

```
GOOGLE_REDIRECT_URI=<new URL>/auth/oauth2/callback/google
FRONTEND_BASE_URL=<new URL>
```

---

**Step 4:** Apply it. This is read at container runtime, not baked into
the image, so no `--build` is needed:

```bash
docker compose -f docker-compose.local-prod.yml up -d
```

Repeating this every restart is usually more friction than it's worth.
Two better options for regular Google login testing: test it against the dev
stack instead (`http://localhost:5173`,
`GOOGLE_REDIRECT_URI=http://localhost:8000/auth/oauth2/callback/google`),
or switch to a [Named Tunnel](#named-tunnel-stable-url) below, where the
URL is stable and this becomes one-time setup.

---

### Named Tunnel (stable URL)

```yaml
command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
```

Requires a domain added to a free Cloudflare account. The domain's DNS
zone must live in *your own* Cloudflare account for tunnel routing to
work. A subdomain donated by a third-party registry repo (`is-a.dev`,
`rweb.site`, etc.) will not work here, since Cloudflare Tunnel resolves the
target tunnel by matching the request against Public Hostname config in
the account that owns the zone: a zone you don't control can't route to
a tunnel it doesn't know about.

**Step 1:** Zero Trust dashboard, then Networks, Tunnels, Create a tunnel,
Cloudflared, name it.

---

**Step 2:** Copy the token from the install step into `TUNNEL_TOKEN` in
`.env`.

---

**Step 3:** Still in that tunnel's config: Public Hostname, Add a public
hostname, your domain or subdomain, Service: HTTP, `http://frontend:80`.

---

**Step 4:** Point `FRONTEND_BASE_URL` and `BACKEND_BASE_URL` in `.env` at
that hostname once it's live. Leave `VITE_API_BASE_URL` empty: frontend
and backend share one public origin behind the tunnel, and nginx
(`docker/nginx.frontend.conf`) proxies API prefixes to `backend`
same-origin, so the browser never needs a separate API URL.

---

**Step 5:** In the [Google Cloud Console](https://console.cloud.google.com/),
under **APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`https://your-hostname/auth/oauth2/callback/google` under **Authorized
redirect URIs** and `https://your-hostname` under **Authorized
JavaScript origins**. Then set `GOOGLE_REDIRECT_URI` in `.env` to that
same redirect URI. It must match byte-for-byte, or login fails with
`redirect_uri_mismatch`.

---

**Step 6:** Edit `docker-compose.local-prod.yml`'s `cloudflared` command to
the `run --token` form above.

---

**Step 7:** Apply the changes:

```bash
docker compose -f docker-compose.local-prod.yml up -d --build
```

Unlike Quick Tunnel, this URL is stable, so steps 4 and 5 are one-time
setup, not something you repeat on every restart. See
[OAuth2 / PKCE](../authentication/oauth2-pkce.md#troubleshooting) if login
still fails after this.

If you don't already own a domain, buying a cheap one (a few dollars a
year, e.g. from Namecheap or Porkbun) and adding its nameservers to your
Cloudflare account is the only way to get a stable custom domain that
actually works with Cloudflare Tunnel. Free third-party subdomain donors
don't give you zone-level control.

---

## Environment variables

`.env.local-prod.example` is the source of truth for local-prod values. It is
set up for Cloudflare Quick Tunnel, same-origin API routing, production mode,
and the fixed frontend nginx proxy IP.

Rotate the secrets in the copied `.env` before real use. Review
`FRONTEND_BASE_URL`, `BACKEND_BASE_URL`, `GOOGLE_REDIRECT_URI`, SMTP,
rate-limit, Redis, and error-monitoring values before sharing the service.

Build-time values must be final before you run `--build`:

- `VITE_API_BASE_URL`: keep empty for the bundled nginx same-origin proxy.
- `VITE_APP_NAME`: public app name shown in the browser.
- `VITE_SENTRY_DSN`: public browser DSN if frontend error reporting is enabled.
- `VITE_SENTRY_ENVIRONMENT`: frontend environment tag.

Runtime values can be changed with a container restart:

- `SECRET_KEY`, `DATABASE_URL`, `POSTGRES_*`, `REDIS_URL`, and
  `REDIS_PASSWORD`
- `FRONTEND_BASE_URL`, `BACKEND_BASE_URL`, `GOOGLE_REDIRECT_URI`
- SMTP settings, rate-limit settings, and backend `SENTRY_DSN`

`VITE_API_BASE_URL`, `VITE_APP_NAME`, `VITE_SENTRY_DSN`, and
`VITE_SENTRY_ENVIRONMENT` are baked in at image build time, not read at
container runtime. Set them in `.env` before `--build`, not after. See
[Deployment Guide: required production environment variables](guide.md#required-production-environment-variables)
for the full explanation of each.

---

## What's different from dev / prod

See [Docker Overview: dev vs. production compose](../docker/overview.md#dev-vs-production-compose)
for the full table. In short: no bind mounts, no reload, `unless-stopped`
restart policy, `alembic` gates `backend`/`taskiq_worker` startup, and TLS
terminates at Cloudflare's edge rather than in a container you run.

Use `docker-compose.prod.yml` instead (see [Prod Deployment](prod.md)) if
you'd rather the host itself own the public IP and terminate TLS via Caddy,
for example on your own server.
