# Local-Prod Deployment

Self-hosted production image/runtime shape from your own machine or home
server. The code is baked into images, reload is off, bind mounts are gone,
and Cloudflare Tunnel exposes the app to the internet without your own public
IP, router port forwarding, or Caddy.

Not sure this is the mode you want? See the
[dev vs. local-prod vs. prod comparison](guide.md#at-a-glance) in the
Deployment Guide.

---

## Which mode do I want?

There are two ways to expose your local-prod stack to the internet, both
via Cloudflare Tunnel. Pick one and follow that section start to finish —
each is a complete, standalone walkthrough, so you don't need to read the
other one first.

- **Quick Tunnel** — zero Cloudflare account, zero domain, up in a couple
  of minutes. The public URL is random and changes every time you restart
  the stack. Good for a quick test.
- **Named Tunnel** — needs a domain on a free Cloudflare account. A bit
  more setup, but the URL is stable, so you configure Google login once
  and never touch it again.

Not sure local-prod itself is the mode you want (vs. dev or prod)? See the
[dev vs. local-prod vs. prod comparison](guide.md#at-a-glance) in the
Deployment Guide.

---

## Option A: Quick Tunnel (zero setup)

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
signup, email verification, and password reset, or Google OAuth2 login. See
[System Superuser](../authentication/system-superuser.md) for the interactive
command, or `local-scripts/local-prod/create-system-user.*` for a
non-interactive version.

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

At this point signup, password login, and browsing already work through
that URL. That's because `VITE_API_BASE_URL` is left empty, so the
frontend calls the API on whatever origin it was loaded from, and nginx
proxies that same-origin request to `backend` internally. Google login
needs a few more steps, since it's the one flow tied to the exact tunnel
URL — continue below to enable it.

---

**Step 4: Copy the URL for Google.**

Copy the URL from Step 3's logs (or re-run
`docker compose -f docker-compose.local-prod.yml logs cloudflared | grep trycloudflare.com`).
You'll paste it into two places in the next two steps.

Unlike every other flow, the OAuth2 callback (`oauth2_login_handler.py`)
issues a hard, cross-origin redirect built from `FRONTEND_BASE_URL` after
setting the auth cookies on the tunnel host. If `FRONTEND_BASE_URL` is
stale (e.g. left at `http://localhost`), the browser gets sent to a
different origin than the one holding the cookies, `/auth/me` comes back
401, and the user is bounced to `/login`, even though the account was
created/verified successfully server-side. That's what Steps 5–6 prevent.

---

**Step 5: Register that URL with Google.**

In the [Google Cloud Console](https://console.cloud.google.com/), under
**APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`<that URL>/auth/oauth2/callback/google` under **Authorized redirect URIs**
and `<that URL>` under **Authorized JavaScript origins**. Old entries from
past restarts can be removed, or left there — Google allows multiple.

---

**Step 6: Point the app at that URL.**

In `.env`, set:

```
GOOGLE_REDIRECT_URI=<that URL>/auth/oauth2/callback/google
FRONTEND_BASE_URL=<that URL>
```

(`FRONTEND_BASE_URL` is also baked into verification/password-reset email
links and the CORS allow-list, so keeping it current matters even beyond
Google login. `BACKEND_BASE_URL` must be *set* for the app to boot, but
nothing reads it at runtime, so it never needs to track the tunnel URL.)

---

**Step 7: Apply it.**

`.env` values here are read at container runtime, not baked into the
image, so a plain restart is enough — **no `--build`**:

```bash
docker compose -f docker-compose.local-prod.yml up -d
```

**The Quick Tunnel URL changes on every restart**, so if you stop and start
the stack again, repeat Steps 4–7 to keep Google login working. If that's
more friction than it's worth, either test Google login against the dev
stack instead (`http://localhost:5173`,
`GOOGLE_REDIRECT_URI=http://localhost:8000/auth/oauth2/callback/google`), or
switch to Option B below, where this is one-time setup.

---

## Option B: Named Tunnel (stable URL)

Requires a domain added to a free Cloudflare account. The domain's DNS
zone must live in *your own* Cloudflare account for tunnel routing to
work. A subdomain donated by a third-party registry repo (`is-a.dev`,
`rweb.site`, etc.) will not work here, since Cloudflare Tunnel resolves the
target tunnel by matching the request against Public Hostname config in
the account that owns the zone: a zone you don't control can't route to
a tunnel it doesn't know about. If you don't already own a domain, buying
a cheap one (a few dollars a year, e.g. from Namecheap or Porkbun) and
adding its nameservers to your Cloudflare account is the only way to get
this working.

**Step 1: Copy the env file.**

```bash
cp .env.local-prod.example .env
```

Same file as Option A — see Step 1 there for what it preconfigures. Do not
start local-prod from `.env.example`; that file is for the dev stack.

---

**Step 2: Create the tunnel in Cloudflare.**

Zero Trust dashboard → Networks → Tunnels → Create a tunnel → Cloudflared
→ name it. Copy the token shown in the install step into `TUNNEL_TOKEN`
in `.env`.

---

**Step 3: Point the tunnel at your app.**

Still in that tunnel's config: Public Hostname → Add a public hostname →
your domain or subdomain → Service: HTTP → `http://frontend:80`.

---

**Step 4: Point the app at that hostname.**

In `.env`, set `FRONTEND_BASE_URL` and `BACKEND_BASE_URL` to
`https://your-hostname` once it's live. Leave `VITE_API_BASE_URL` empty:
frontend and backend share one public origin behind the tunnel, and nginx
(`docker/nginx.frontend.conf`) proxies API prefixes to `backend`
same-origin, so the browser never needs a separate API URL.

---

**Step 5: Register the hostname with Google and enable Google login.**

In the [Google Cloud Console](https://console.cloud.google.com/), under
**APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`https://your-hostname/auth/oauth2/callback/google` under **Authorized
redirect URIs** and `https://your-hostname` under **Authorized
JavaScript origins**. Then set `GOOGLE_REDIRECT_URI` in `.env` to that
same redirect URI. It must match byte-for-byte, or login fails with
`redirect_uri_mismatch`.

---

**Step 6: Switch the compose file to Named Tunnel mode.**

Edit `docker-compose.local-prod.yml`'s `cloudflared` service `command:`
from the Quick Tunnel form to:

```yaml
command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
```

---

**Step 7: Start (or restart) the stack.**

```bash
docker compose -f docker-compose.local-prod.yml up -d --build
```

Open `https://your-hostname` in a browser — that's your app, live at a
stable address. Unlike Quick Tunnel, this URL doesn't change, so Steps 4
and 5 are one-time setup, not something you repeat on every restart. See
[OAuth2 / PKCE](../authentication/oauth2-pkce.md#troubleshooting) if login
still fails after this.

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
restart policy, `alembic` gates `backend`/`taskiq_worker`/`taskiq_scheduler` startup, and TLS
terminates at Cloudflare's edge rather than in a container you run.

Use `docker-compose.prod.yml` instead (see [Prod Deployment](prod.md)) if
you'd rather the host itself own the public IP and terminate TLS via Caddy,
for example on your own server.
