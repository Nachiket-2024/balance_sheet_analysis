# Cloudflare Named Tunnel (stable URL)
---

See [Local-Prod Deployment](README.md) for the mode chooser, environment
variables, and how local-prod differs from dev/prod. This page is the
stable-URL Cloudflare Named Tunnel walkthrough, start to finish.

---

## Files used by this guide

| File | Why it matters |
|---|---|
| `docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml` plus `docker/app/compose/docker-compose.local-prod-cloudflare.yml` | The upstream file defines the stack; your app override changes the `cloudflared` command to Named Tunnel mode without editing upstream. |
| `env/mystic_auth/.env.local-prod-cloudflare.example` | Source template for Cloudflare local-prod settings, including `TUNNEL_TOKEN`. |
| `env/mystic_auth/.env.local-prod-cloudflare` | Your local, gitignored copy with the tunnel token, public hostname, Google callback, and secrets. |
| `scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.*` | Compose helpers that always pass the Cloudflare env file. |
| `local-scripts/mystic_auth/local-prod-cloudflare/create-system-user.*` | Optional non-interactive system-superuser creation scripts. |

---

## Platform setup

This guide uses the app-owned Compose override. Keep the tracked
`docker/mystic_auth/` file unchanged so future upstream syncs remain clean.

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

Cloudflare Named Tunnel uses the same `cloudflared` container as Quick
Tunnel, but it authenticates with a persistent tunnel token:

```yaml
command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
```

Traffic enters Cloudflare at `https://your-hostname`, then Cloudflare routes
that hostname to the named tunnel, and `cloudflared` forwards it to
`http://frontend:80` inside Docker.

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    S1["1. Copy\nenv.local-prod-cloudflare.example"]
    S2["2. Create the tunnel\nin Cloudflare"]
    S3["3. Point the tunnel\nat your app"]
    S4["4. Point the app at\nthat hostname\nFRONTEND_BASE_URL, JWT_ISSUER/AUDIENCE"]
    S5["5. Register the hostname\nwith Google OAuth"]
    S6["6. Switch compose file\nto Named Tunnel mode"]
    S7["7. Start (or restart)\nthe stack"]
    S7b["7b (optional): enable\nsession geolocation"]
    Live["Public https://<your-domain>"]

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S7b --> Live

    classDef terminal fill:#dcfce7,stroke:#16a34a,color:#14532d
    class Live terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

---

**Step 1: Copy both env files.**

```bash
cp env/mystic_auth/.env.local-prod-cloudflare.example env/mystic_auth/.env.local-prod-cloudflare
cp env/app/.env.local-prod-cloudflare.example env/app/.env.local-prod-cloudflare
```

Same file as [Cloudflare Quick Tunnel](cloudflare-quick-tunnel.md): see Step 1 there for what it
preconfigures. Do not start local-prod from `env/mystic_auth/.env.dev.example`; that file is for
the dev stack.

---

**Step 2: Create the tunnel in Cloudflare.**

Zero Trust dashboard → Networks → Tunnels → Create a tunnel → Cloudflared
→ name it. Copy the token shown in the install step into `TUNNEL_TOKEN`
in `env/mystic_auth/.env.local-prod-cloudflare`.

---

**Step 3: Point the tunnel at your app.**

Still in that tunnel's config: Public Hostname → Add a public hostname →
your domain or subdomain → Service: HTTP → `http://frontend:80`.

---

**Step 4: Point the app at that hostname.**

In `env/mystic_auth/.env.local-prod-cloudflare`, set `FRONTEND_BASE_URL` and `BACKEND_BASE_URL` to
`https://your-hostname` once it's live. Leave `VITE_API_BASE_URL` empty:
frontend and backend share one public origin behind the tunnel, and nginx
(`docker/mystic_auth/nginx.frontend.conf`) proxies API prefixes to `backend`
same-origin, so the browser never needs a separate API URL.

Also set `JWT_ISSUER` and `JWT_AUDIENCE` to `https://your-hostname`. They
don't have to match `FRONTEND_BASE_URL` for tokens to work (they're only
checked against themselves, see
[Authentication Overview](../../authentication/overview.md)), but leaving
them at the placeholder default means every deployment that copies this
tutorial mints tokens with the same `iss`/`aud`.

---

**Step 5: Register the hostname with Google and enable Google login.**

In the [Google Cloud Console](https://console.cloud.google.com/), under
**APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`https://your-hostname/auth/oauth2/callback/google` under **Authorized
redirect URIs** and `https://your-hostname` under **Authorized
JavaScript origins**. Then set `GOOGLE_REDIRECT_URI` in `env/mystic_auth/.env.local-prod-cloudflare` to that
same redirect URI. It must match byte-for-byte, or login fails with
`redirect_uri_mismatch`.

---

**Step 6: Switch the app Compose override to Named Tunnel mode.**

Edit `docker/app/compose/docker-compose.local-prod-cloudflare.yml` to:

```yaml
services:
  cloudflared:
    command:
      - tunnel
      - --no-autoupdate
      - run
      - --token
      - ${TUNNEL_TOKEN}
```

This override replaces only the upstream service command. The matching
`local-prod-cloudflare-up` helper already passes both Compose files and both
env files.

---

**Step 7: Start (or restart) the stack.**

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare up -d --build
# or: ./scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.sh
```

Open `https://your-hostname` in a browser: that's your app, live at a
stable address. Unlike Quick Tunnel, this URL doesn't change, so Steps 4
and 5 are one-time setup, not something you repeat on every restart. See
[OAuth2 / PKCE](../../authentication/oauth2-pkce.md#troubleshooting) if login
still fails after this.

---

**Step 7b (Optional): Enable session geolocation.**

Setting `GEOIP_DB_PATH`/`GEOIPUPDATE_ACCOUNT_ID`/`GEOIPUPDATE_LICENSE_KEY` in
`env/mystic_auth/.env.local-prod-cloudflare` alone does nothing: the `geoipupdate` service that downloads the
`.mmdb` file is gated behind the `geoip` Compose profile, skipped by Step 7's
command as written. Re-run Step 7 with the profile added instead:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare --profile geoip up -d --build
```

Without it, the updater is not started and Manage Sessions' Location column
shows "Unknown". When the profile is enabled, the updater healthcheck now
requires a non-empty database and becomes unhealthy if the download fails. See
[Session Geolocation](../../geolocation/overview.md)
for the MaxMind account/license-key setup this depends on.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Cloudflare hostname returns 404 or tunnel not found | Public Hostname is not attached to the tunnel that owns `TUNNEL_TOKEN`. | In Cloudflare Zero Trust, open the tunnel, then verify Public Hostname points to `http://frontend:80`. |
| DNS does not resolve your hostname | Domain nameservers are not delegated to your Cloudflare account or DNS has not propagated yet. | Check the domain in Cloudflare DNS and wait for delegation. New domains can take longer than the tunnel setup itself. |
| `cloudflared` exits immediately | `TUNNEL_TOKEN` is missing or invalid. | Copy the token from the tunnel install step into `env/mystic_auth/.env.local-prod-cloudflare`, then restart the stack. |
| Google login returns `redirect_uri_mismatch` | Google Cloud Console callback does not match `GOOGLE_REDIRECT_URI`. | Register `https://your-hostname/auth/oauth2/callback/google` under Authorized redirect URIs. |
| API calls return 502 after changing backend env values | nginx cached the previous backend container IP. | Recreate `backend` and `frontend` together with `--force-recreate`. |

---
