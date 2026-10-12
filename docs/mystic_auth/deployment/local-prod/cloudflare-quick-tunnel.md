# Cloudflare Quick Tunnel (zero setup)
---

See [Local-Prod Deployment](README.md) for the mode chooser, environment
variables, and how local-prod differs from dev/prod. This page is the
zero-setup Cloudflare Quick Tunnel walkthrough, start to finish.

---

## Files used by this guide

| File | Why it matters |
|---|---|
| `docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml` + `docker/app/compose/docker-compose.local-prod-cloudflare.yml` | The upstream file runs the local-prod stack and `cloudflared` Quick Tunnel; the app override is the downstream extension point. |
| `env/mystic_auth/.env.local-prod-cloudflare.example` | Source template for the Cloudflare local-prod runtime and build settings. |
| `env/mystic_auth/.env.local-prod-cloudflare` + `env/app/.env.local-prod-cloudflare` | Your local, gitignored runtime files with template settings, app settings, secrets, and public URLs. |
| `scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.sh` | Linux/macOS/Git Bash helper that wraps the full Compose command. |
| `scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.ps1` | PowerShell helper. |
| `scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.cmd` | Command Prompt helper. |
| `local-scripts/mystic_auth/local-prod-cloudflare/create-system-user.*` | Optional non-interactive system-superuser creation scripts. |

---

## Platform setup

Cloudflare Quick Tunnel does not require a Cloudflare account or a domain. The `cloudflared` container runs:

```yaml
command: tunnel --no-autoupdate --url http://frontend:80
```

Cloudflare allocates a temporary `https://<random-words>.trycloudflare.com` URL and proxies it to `frontend:80` inside Docker. TLS terminates at Cloudflare's edge. The frontend nginx container then proxies API prefixes to `backend:8000`.

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    S1["1. Copy\nenv.local-prod-cloudflare.example"]
    S2["2. Start the stack"]
    S2b["2b (optional): enable\nsession geolocation"]
    Basic["Signup/password login\nalready work\n(same-origin proxy)"]
    S3["3. Get the public URL\nfrom cloudflared logs\n(random, changes every restart)"]
    Google{"Google login\nwanted?"}
    S4["4. Copy that URL"]
    S5["5. Register it\nwith Google OAuth"]
    S6["6. Point the app\nat that URL"]
    S7["7. Apply it\n--force-recreate backend frontend"]
    Live["Live, Google login working"]

    S1 --> S2 --> S2b --> S3 --> Basic
    S3 --> Google
    Google -- "no" --> Basic
    Google -- "yes" --> S4 --> S5 --> S6 --> S7 --> Live
    Live -.->|"stack restarted:\nURL changed, repeat 3-7"| S3

    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    classDef terminal fill:#dcfce7,stroke:#16a34a,color:#14532d
    class Google decision
    class Basic,Live terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

---

**Step 1: Copy both env files.**

```bash
cp env/mystic_auth/.env.local-prod-cloudflare.example env/mystic_auth/.env.local-prod-cloudflare
cp env/app/.env.local-prod-cloudflare.example env/app/.env.local-prod-cloudflare
```

`env/mystic_auth/.env.local-prod-cloudflare.example` is the local-prod template for
the upstream `docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml`. The matching `env/app/` file is where downstream-only values belong. The stack is preconfigured for Quick Tunnel; run it with the matching `docker/app/compose/docker-compose.local-prod-cloudflare.yml` override:

- `VITE_API_BASE_URL` is empty for same-origin API calls.
- `TRUSTED_PROXY_IPS` (derived automatically from `FRONTEND_STATIC_IP`/`CLOUDFLARED_STATIC_IP`) matches the fixed frontend nginx address.
- You can boot before filling in Google or SMTP credentials. The CLI-created system superuser can still sign in and view the dashboard because the script marks it verified.
- Regular users need one verification path: SMTP for password signup, email verification, and password reset, or Google OAuth2 login. See [System Superuser](../../authentication/system-superuser/README.md) for the interactive command, or `local-scripts/mystic_auth/local-prod-cloudflare/create-system-user.*` for a non-interactive version.

Do not start local-prod from `env/mystic_auth/.env.dev.example`. That file points the frontend at
localhost dev ports and leaves production routing values unset. See
[Choosing the right env template](../environment.md#1-choosing-the-right-env-template)
for the mode comparison.

---

**Step 2: Start the stack.**

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare up -d --build
# or: ./scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.sh
```

---

**Step 2b (Optional): Enable session geolocation.**

Setting `GEOIP_DB_PATH`/`GEOIPUPDATE_ACCOUNT_ID`/`GEOIPUPDATE_LICENSE_KEY` in
`env/mystic_auth/.env.local-prod-cloudflare` alone does nothing. The `geoipupdate` service that downloads the
`.mmdb` file is gated behind the `geoip` Compose profile, skipped by Step 2's
command as written. Re-run Step 2 with the profile added instead:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare --profile geoip up -d --build
```

Without it, the updater is not started and Manage Sessions' Location column
shows "Unknown". When the profile is enabled, the updater healthcheck now
requires a non-empty database and becomes unhealthy if the download fails. See
[Session Geolocation](../../geolocation/overview.md)
for the MaxMind account/license-key setup this depends on.

---

**Step 3: Get your public URL.**

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare logs -f cloudflared
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
URL: continue below to enable it.

---

**Step 4: Copy the URL for Google.**

Copy the URL from Step 3's logs (or re-run
`docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare logs cloudflared | grep trycloudflare.com`).
You'll paste it into two places in the next two steps.

Unlike every other flow, the OAuth2 callback (`oauth2_login_handler.py`)
issues a hard, cross-origin redirect built from `FRONTEND_BASE_URL` after
setting the auth cookies on the tunnel host. If `FRONTEND_BASE_URL` is
stale (e.g. left at `http://localhost`), the browser gets sent to a
different origin than the one holding the cookies, `/auth/me` comes back
401, and the user is bounced to `/login`, even though the account was
created/verified successfully server-side. That's what Steps 5-6 prevent.

---

**Step 5: Register that URL with Google.**

In the [Google Cloud Console](https://console.cloud.google.com/), under
**APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`<that URL>/auth/oauth2/callback/google` under **Authorized redirect URIs**
and `<that URL>` under **Authorized JavaScript origins**. Old entries from
past restarts can be removed, or left there (Google allows multiple).

---

**Step 6: Point the app at that URL.**

In `env/mystic_auth/.env.local-prod-cloudflare`, set:

```
GOOGLE_REDIRECT_URI=<that URL>/auth/oauth2/callback/google
FRONTEND_BASE_URL=<that URL>
JWT_ISSUER=<that URL>
JWT_AUDIENCE=<that URL>
```

(`FRONTEND_BASE_URL` is also baked into verification/password-reset email
links and the CORS allow-list, so keeping it current matters even beyond
Google login. `BACKEND_BASE_URL` must identify the backend/API origin because
the backend uses its hostname for trusted-host validation. With the
same-origin proxy setup it normally matches `FRONTEND_BASE_URL`.
`JWT_ISSUER`/`JWT_AUDIENCE` don't have to match `FRONTEND_BASE_URL` for
tokens to work (they're only checked against themselves, see
[Authentication Overview](../../authentication/overview.md)), but a Quick
Tunnel URL changes on every restart, so if you'd rather not re-set these
every time, leave them at a stable placeholder instead.)

---

**Step 7: Apply it.**

`env/mystic_auth/.env.local-prod-cloudflare` values here are read at container runtime, not baked into the
image, so a plain restart is enough (**no `--build`**). Restart `backend` and `frontend` together, not
just `backend` alone, and use `--force-recreate` on both:

- `frontend`'s nginx resolves the `backend` hostname to a Docker-internal IP once, when nginx starts, and keeps using it. A `backend`-only restart leaves nginx proxying to the old, now-dead IP once `backend` comes back on a new one - a Cloudflare 502 on every API call, including plain password login, not just Google's, with `docker logs <frontend container>` showing `connect() failed (111: Connection refused) while connecting to upstream`.
- Plain `up -d backend frontend` isn't enough on its own either: Compose only recreates a container whose *own* config changed, and frontend's config didn't - only backend's env did - so frontend would silently keep running unchanged, DNS cache and all.
- `--force-recreate` makes both actually restart regardless, sidestepping the whole problem in one command:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare up -d --force-recreate backend frontend
```
---

**The Quick Tunnel URL changes on every restart**, so if you stop and start
the stack again, repeat Steps 4-7 to keep Google login working. If that's
more friction than it's worth, either test Google login against the dev
stack instead (`http://localhost:5173`,
`GOOGLE_REDIRECT_URI=http://localhost:8000/auth/oauth2/callback/google`), or
switch to [Cloudflare Named Tunnel](cloudflare-named-tunnel.md), where this is one-time setup,
or try [ngrok](ngrok-tunnel.md) or [Tailscale Funnel](tailscale-funnel.md) instead, which are
also free and also give you a stable URL.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `cloudflared` logs do not show a `trycloudflare.com` URL | Tunnel container has not started or cannot reach Cloudflare. | Run `docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare logs -f cloudflared` and check network access from the host. |
| Public URL shows Cloudflare 502 | `cloudflared` can reach the tunnel edge but cannot reach `frontend:80`. | Check `docker compose ... ps`, then `docker compose ... logs frontend backend`. Recreate `frontend` and `backend` together if backend was restarted. |
| Password login works locally but not through the tunnel | `FRONTEND_BASE_URL`, CORS, or cookie origin settings are stale. | Set `FRONTEND_BASE_URL` to the active Quick Tunnel URL and recreate `backend` and `frontend`. |
| Google login returns `redirect_uri_mismatch` | Google has a different callback URL than `GOOGLE_REDIRECT_URI`. | Register the current `<quick-url>/auth/oauth2/callback/google` in Google Cloud Console and update `GOOGLE_REDIRECT_URI`. |
| Manage Sessions location shows `Unknown` | GeoIP profile was not enabled, the updater is still downloading, or the `.mmdb` file is missing. | Start with `--profile geoip`, inspect `geoipupdate` health/logs, and verify the non-empty `.mmdb` file after setting `GEOIPUPDATE_ACCOUNT_ID`, `GEOIPUPDATE_LICENSE_KEY`, and `GEOIP_DB_PATH`. |

---
