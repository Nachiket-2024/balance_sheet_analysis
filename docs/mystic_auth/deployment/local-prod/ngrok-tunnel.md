# ngrok Tunnel (stable URL, no Cloudflare account)

---

See [Local-Prod Deployment](README.md) for the mode chooser, environment
variables, and how local-prod differs from dev/prod. This page is the ngrok
walkthrough, start to finish.

---

## Files used by this guide

| File | Why it matters |
|---|---|
| `docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml` + `docker/app/compose/docker-compose.local-prod-ngrok.yml` | The upstream file runs the local-prod stack and `ngrok`; the app override is the downstream extension point. |
| `env/mystic_auth/.env.local-prod-ngrok.example` | Source template for ngrok local-prod settings. |
| `env/mystic_auth/.env.local-prod-ngrok` + `env/app/.env.local-prod-ngrok` | Your local, gitignored runtime files with `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`, app settings, public URLs, Google callback, and secrets. |
| `scripts/mystic_auth/docker/local-prod-ngrok/local-prod-ngrok-up.*` | Compose helpers that always pass both the MysticAuth and app-owned ngrok env files. |
| `local-scripts/mystic_auth/local-prod-ngrok/create-system-user.*` | Optional non-interactive system-superuser creation scripts. |

---

## Platform setup

A free ngrok account, its authtoken, and a free static domain are required
before the tunnel comes up at all. ngrok's free tier issues one static
domain per account, and the `ngrok` service in
`docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml` is pinned to it with
`--url=https://${NGROK_DOMAIN}` in its `command:`, so the URL is stable
from the first boot and Steps 1-6 below are one-time setup, not something
to repeat on every restart.

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    S1["1. Create a free ngrok\naccount, grab authtoken"]
    S2["2. Claim a free\nstatic domain"]
    S3["3. Copy env.local-prod-ngrok.example"]
    S4["4. Fill in\nNGROK_AUTHTOKEN, NGROK_DOMAIN"]
    S5["5. Point the app at that domain\nFRONTEND_BASE_URL, JWT_ISSUER/AUDIENCE,\nGOOGLE_REDIRECT_URI"]
    S6["6. Register the domain\nwith Google OAuth"]
    S7["7. Start the stack"]
    S7b["7b (optional): enable\nsession geolocation"]
    Live["Public https://<app>.ngrok-free.app"]

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S7b --> Live

    classDef terminal fill:#dcfce7,stroke:#16a34a,color:#14532d
    class Live terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

---

**Step 1: Create a free ngrok account and grab your authtoken.**

Sign up at [ngrok.com](https://ngrok.com/) (a free account is enough).
Then, in the [ngrok dashboard](https://dashboard.ngrok.com/), go to
**Getting Started → Your Authtoken** and copy it.

---

**Step 2: Claim a free static domain.**

In the dashboard, go to **Domains** and create a free static domain, e.g.
`my-app.ngrok-free.app`. Unlike ngrok's older random-URL tunnels, this
domain does not change between restarts.

---

**Step 3: Copy both env files.**

```bash
cp env/mystic_auth/.env.local-prod-ngrok.example env/mystic_auth/.env.local-prod-ngrok
cp env/app/.env.local-prod-ngrok.example env/app/.env.local-prod-ngrok
```

`env/mystic_auth/.env.local-prod-ngrok.example` is the local-prod template for
`docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml`. It preconfigures
same-origin API routing (`VITE_API_BASE_URL` empty) and the fixed frontend
nginx proxy IP (`TRUSTED_PROXY_IPS`, derived automatically from
`FRONTEND_STATIC_IP`/`NGROK_STATIC_IP`). Put downstream-only values in the matching
`env/app/` file. Do not start
this stack from `env/mystic_auth/.env.dev.example` or `env/mystic_auth/.env.local-prod-cloudflare.example`;
those are dev's and Cloudflare's files respectively. See
[Choosing the right env template](../environment.md#1-choosing-the-right-env-template)
for the full comparison.

---

**Step 4: Fill in your authtoken and domain.**

In the copied `env/mystic_auth/.env.local-prod-ngrok`, set:

```
NGROK_AUTHTOKEN=<the authtoken from Step 1>
NGROK_DOMAIN=<your-app>.ngrok-free.app
```

Both are required.

---

**Step 5: Point the app at that domain.**

Still in `env/mystic_auth/.env.local-prod-ngrok`, set:

```
GOOGLE_REDIRECT_URI=https://<your-app>.ngrok-free.app/auth/oauth2/callback/google
FRONTEND_BASE_URL=https://<your-app>.ngrok-free.app
JWT_ISSUER=https://<your-app>.ngrok-free.app
JWT_AUDIENCE=https://<your-app>.ngrok-free.app
```

- `FRONTEND_BASE_URL` is baked into verification/password-reset email links and the CORS allow-list too, so it matters even if you never enable Google login.
- `BACKEND_BASE_URL` must identify the backend/API origin because the backend uses its hostname for trusted-host validation. It normally matches `FRONTEND_BASE_URL` when ngrok exposes the same-origin proxy.
- `JWT_ISSUER`/`JWT_AUDIENCE` don't have to match `FRONTEND_BASE_URL` for tokens to work (they're only checked against themselves, see [Authentication Overview](../../authentication/overview.md)), but leaving them at the placeholder default means every deployment that copies this tutorial mints tokens with the same `iss`/`aud`, so update them to this deployment's real domain too.

---

**Step 6: Register the domain with Google and enable Google login.**

In the [Google Cloud Console](https://console.cloud.google.com/), under
**APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`https://<your-app>.ngrok-free.app/auth/oauth2/callback/google` under
**Authorized redirect URIs** and `https://<your-app>.ngrok-free.app` under
**Authorized JavaScript origins**. It must match `GOOGLE_REDIRECT_URI`
byte-for-byte, or login fails with `redirect_uri_mismatch`.

---

**Step 7: Start the stack.**

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml -f docker/app/compose/docker-compose.local-prod-ngrok.yml --env-file env/mystic_auth/.env.local-prod-ngrok --env-file env/app/.env.local-prod-ngrok up -d --build
# or: ./scripts/mystic_auth/docker/local-prod-ngrok/local-prod-ngrok-up.sh
```

Open `https://<your-app>.ngrok-free.app` in a browser: that's your app,
live on the internet, at a URL that stays the same across restarts. See
[OAuth2 / PKCE](../../authentication/oauth2-pkce.md#troubleshooting) if login
still fails after this.

`frontend` (port 8180) and `backend` (port 8101) are also published to the
host for local debugging, but the public entrypoint is the `ngrok` service,
not those ports.

---

**Step 7b (Optional): Enable session geolocation.**

Setting `GEOIP_DB_PATH`/`GEOIPUPDATE_ACCOUNT_ID`/`GEOIPUPDATE_LICENSE_KEY` in
`env/mystic_auth/.env.local-prod-ngrok` alone does nothing: the `geoipupdate` service
that downloads the `.mmdb` file is gated behind the `geoip` Compose
profile, skipped by Step 7's command as written. Re-run Step 7 with the
profile added instead:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml -f docker/app/compose/docker-compose.local-prod-ngrok.yml --env-file env/mystic_auth/.env.local-prod-ngrok --env-file env/app/.env.local-prod-ngrok --profile geoip up -d --build
```

Without it, the updater is not started and Manage Sessions' Location column
shows "Unknown". When the profile is enabled, the updater healthcheck now
requires a non-empty database and becomes unhealthy if the download fails. See
[Session Geolocation](../../geolocation/overview.md)
for the MaxMind account/license-key setup this depends on.

---

## Bugsink stays private

`bugsink` (self-hosted error monitoring) binds to `127.0.0.1:8111` only, not
the ngrok tunnel: `ngrok` in this file proxies `frontend:80` alone. Reach
Bugsink locally at `http://localhost:8111`, or over SSH port-forwarding if
this is a remote host.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ngrok` container exits | `NGROK_AUTHTOKEN` or `NGROK_DOMAIN` is missing or invalid. | Check `env/mystic_auth/.env.local-prod-ngrok`, then run `docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml -f docker/app/compose/docker-compose.local-prod-ngrok.yml --env-file env/mystic_auth/.env.local-prod-ngrok --env-file env/app/.env.local-prod-ngrok logs ngrok`. |
| Public URL returns an ngrok error page | The static domain is not assigned to your ngrok account or the tunnel is not running. | Confirm the domain in the ngrok dashboard and restart the stack. |
| Google login returns `redirect_uri_mismatch` | Google Cloud Console callback does not match `GOOGLE_REDIRECT_URI`. | Register `https://<your-app>.ngrok-free.app/auth/oauth2/callback/google`. |
| API calls fail but the landing page loads | nginx or backend is unhealthy inside Docker. | Check `docker compose ... ps`, `docker compose ... logs frontend backend`, and the backend ready check on `http://localhost:8101/health/ready`. |
| Bugsink is not reachable through ngrok | This is expected. The tunnel only exposes `frontend:80`. | Use `http://localhost:8111` on the host or an SSH port-forward. |

---
