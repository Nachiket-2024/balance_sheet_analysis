# Tailscale Funnel (stable URL, no public server)

---

See [Local-Prod Deployment](README.md) for the mode chooser, environment
variables, and how local-prod differs from dev/prod. This page is the
Tailscale Funnel walkthrough, start to finish.

Official references for the platform behavior used here:

1. [Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel)
2. [Tailscale Docker](https://tailscale.com/docs/features/containers/docker)
3. [Docker configuration parameters](https://tailscale.com/docs/features/containers/docker/docker-params)
4. [Tailscale DNS](https://tailscale.com/docs/reference/dns-in-tailscale)
5. [HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates)

Tailscale Funnel exposes one service on your own machine to the public
internet at a stable `https://<hostname>.<tailnet>.ts.net` URL, through your
free [Tailscale](https://tailscale.com/) account, with TLS handled for you.
Like ngrok, there is no zero-setup anonymous mode: a free Tailscale account
and an auth key are required before the tunnel comes up.

---

## Files used by this guide

| File | Why it matters |
|---|---|
| `docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml` + `docker/app/compose/docker-compose.local-prod-tailscale.yml` | The upstream file runs the local-prod stack and `tailscale/tailscale`; the app override is the downstream extension point. |
| `docker/tailscale-serve-config.json` | Programmatic Serve/Funnel config mounted into the Tailscale container through `TS_SERVE_CONFIG`. |
| `env/mystic_auth/.env.local-prod-tailscale.example` | Source template for Tailscale local-prod settings. |
| `env/mystic_auth/.env.local-prod-tailscale` + `env/app/.env.local-prod-tailscale` | Your local, gitignored runtime files with `TS_AUTHKEY`, `TS_HOSTNAME`, app settings, public URLs, Google callback, and secrets. |
| `scripts/mystic_auth/docker/local-prod-tailscale/local-prod-tailscale-up.*` | Compose helpers that always pass both the MysticAuth and app-owned Tailscale env files. |
| `local-scripts/mystic_auth/local-prod-tailscale/create-system-user.*` | Optional non-interactive system-superuser creation scripts. |

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    S1["1. Create a free\nTailscale account"]
    S2["2. Generate an auth key"]
    S3["3. Enable Funnel\nfor your tailnet"]
    S4["4. Copy\nenv.local-prod-tailscale.example"]
    S5["5. Fill in auth key,\nhostname"]
    S5b["5b: understand\nURL timing"]
    S6["6. Point the app at\nthat hostname"]
    S7["7. Register the hostname\nwith Google OAuth"]
    S8["8. Start (or restart)\nthe stack"]
    S8b["8b (optional): enable\nsession geolocation"]
    Live["Public Tailscale Funnel URL"]

    S1 --> S2 --> S3 --> S4 --> S5 --> S5b --> S6 --> S7 --> S8 --> S8b --> Live

    classDef terminal fill:#dcfce7,stroke:#16a34a,color:#14532d
    class Live terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

---

**Step 1: Create a free Tailscale account.**

Sign up at [tailscale.com](https://tailscale.com/) (a free "Personal" plan
is enough). This gives you a tailnet: your own private network name, shown
in the admin console as `<something>.ts.net`.

---

**Step 2: Generate an auth key.**

In the [Tailscale admin console](https://login.tailscale.com/admin/settings/keys),
go to **Settings → Keys → Generate auth key**. A reusable key is simplest
for this stack, since the `tailscale` container re-registers using the same
key on every restart. Copy the generated key; it is shown only once.

---

**Step 3: Enable Funnel for your tailnet.**

Funnel is off by default. In the admin console:

1. Open **DNS**.
2. Enable **MagicDNS** if it is not already enabled.
3. Enable **HTTPS Certificates**.
4. Enable **Funnel** for the tailnet.

Without HTTPS certificates enabled, the `tailscale` container cannot provision
the certificate for the `.ts.net` name used by `AllowFunnel`, and public Funnel
traffic never reaches `frontend`.

---

**Step 4: Copy both env files.**

```bash
cp env/mystic_auth/.env.local-prod-tailscale.example env/mystic_auth/.env.local-prod-tailscale
cp env/app/.env.local-prod-tailscale.example env/app/.env.local-prod-tailscale
```

`env/mystic_auth/.env.local-prod-tailscale.example` is the local-prod template for
`docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml`. It preconfigures
same-origin API routing (`VITE_API_BASE_URL` empty) and the fixed frontend
nginx proxy IP (`TRUSTED_PROXY_IPS`, derived automatically from
`FRONTEND_STATIC_IP`/`TAILSCALE_STATIC_IP`). Put downstream-only values in the matching
`env/app/` file. Do not start
this stack from `env/mystic_auth/.env.dev.example` or either of the other two local-prod
example files. See
[Choosing the right env template](../environment.md#1-choosing-the-right-env-template)
for the full comparison.

---

**Step 5: Fill in your auth key and hostname.**

In the copied `env/mystic_auth/.env.local-prod-tailscale`, set:

```
TS_AUTHKEY=<the auth key from Step 2>
TS_HOSTNAME=mystic-auth
```

`TS_HOSTNAME` becomes the subdomain of your final URL
(`https://mystic-auth.<tailnet>.ts.net`); change it if that name is already
taken on your tailnet, or if you'd rather it be something else.

---

**Step 5b: Understand URL timing.**

On a healthy setup, the Tailscale container usually appears in the Machines
list within 10-30 seconds after the stack starts. The public Funnel URL can
take longer to become usable because three things need to settle:

1. The container authenticates with `TS_AUTHKEY`.
2. Tailscale registers the machine name from `TS_HOSTNAME`.
3. Tailscale provisions HTTPS certificate and DNS records for the `.ts.net`
   name.

Expect the private tailnet name to resolve first. The public Funnel URL often
starts working within 30-90 seconds, but allow a few minutes before treating it
as broken. If the URL still does not resolve after several minutes, use the
troubleshooting section below.

---

**Step 6: Point the app at that hostname.**

You need the exact `.ts.net` domain before this step: start the stack once
first (Step 8), check `docker compose ... logs tailscale` for the assigned
name, or read it from the admin console's device list under **Machines**
once `tailscale` registers. Then set, in `env/mystic_auth/.env.local-prod-tailscale`:

```
GOOGLE_REDIRECT_URI=https://mystic-auth.<tailnet>.ts.net/auth/oauth2/callback/google
FRONTEND_BASE_URL=https://mystic-auth.<tailnet>.ts.net
JWT_ISSUER=https://mystic-auth.<tailnet>.ts.net
JWT_AUDIENCE=https://mystic-auth.<tailnet>.ts.net
```

- `FRONTEND_BASE_URL` is baked into verification/password-reset email links and the CORS allow-list too, so it matters even if you never enable Google login.
- `BACKEND_BASE_URL` must identify the backend/API origin because the backend uses its hostname for trusted-host validation. It normally matches `FRONTEND_BASE_URL` when Tailscale exposes the same-origin proxy.
- `JWT_ISSUER`/`JWT_AUDIENCE` don't have to match `FRONTEND_BASE_URL` for tokens to work (they're only checked against themselves, see [Authentication Overview](../../authentication/overview.md)), but leaving them at the placeholder default means every deployment that copies this tutorial mints tokens with the same `iss`/`aud`, so update them to this deployment's real domain too.

---

**Step 7: Register the hostname with Google and enable Google login.**

In the [Google Cloud Console](https://console.cloud.google.com/), under
**APIs & Services**, **Credentials**, your OAuth 2.0 Client ID, add
`https://mystic-auth.<tailnet>.ts.net/auth/oauth2/callback/google` under
**Authorized redirect URIs** and `https://mystic-auth.<tailnet>.ts.net`
under **Authorized JavaScript origins**. It must match
`GOOGLE_REDIRECT_URI` byte-for-byte, or login fails with
`redirect_uri_mismatch`.

---

**Step 8: Start (or restart) the stack.**

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml -f docker/app/compose/docker-compose.local-prod-tailscale.yml --env-file env/mystic_auth/.env.local-prod-tailscale --env-file env/app/.env.local-prod-tailscale up -d --build
# or: ./scripts/mystic_auth/docker/local-prod-tailscale/local-prod-tailscale-up.sh
```

Open `https://mystic-auth.<tailnet>.ts.net` in a browser: that's your app,
live on the internet, at a URL that stays the same across restarts. See
[OAuth2 / PKCE](../../authentication/oauth2-pkce.md#troubleshooting) if login
still fails after this.

`frontend` (port 8280) and `backend` (port 8201) are also published to the
host for local debugging, but the public entrypoint is Funnel, not those
ports.

---

**Step 8b (Optional): Enable session geolocation.**

Setting `GEOIP_DB_PATH`/`GEOIPUPDATE_ACCOUNT_ID`/`GEOIPUPDATE_LICENSE_KEY` in
`env/mystic_auth/.env.local-prod-tailscale` alone does nothing: the `geoipupdate`
service that downloads the `.mmdb` file is gated behind the `geoip`
Compose profile, skipped by Step 8's command as written. Re-run Step 8 with
the profile added instead:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml -f docker/app/compose/docker-compose.local-prod-tailscale.yml --env-file env/mystic_auth/.env.local-prod-tailscale --env-file env/app/.env.local-prod-tailscale --profile geoip up -d --build
```

Without it, the updater is not started and Manage Sessions' Location column
shows "Unknown". When the profile is enabled, the updater healthcheck now
requires a non-empty database and becomes unhealthy if the download fails. See
[Session Geolocation](../../geolocation/overview.md)
for the MaxMind account/license-key setup this depends on.

---

## How the routing config works

`docker/tailscale-serve-config.json` is the actual proxy config, mounted
read-only into the `tailscale` container and pointed at by
`TS_SERVE_CONFIG=/config/serve-config.json`. Tailscale documents
`TS_SERVE_CONFIG` as the Docker environment variable for programmatic
Serve/Funnel configuration.

The config routes all HTTPS traffic on port 443 to `http://frontend:80` and
sets `AllowFunnel` for the tailnet's own `${TS_CERT_DOMAIN}`. That value is a
Tailscale container-template variable filled in with your assigned `.ts.net`
name at startup. It is not a Docker Compose substitution. The file is mounted
as-is, untouched by Compose. You do not need to edit this file for the default
single-service setup above.

`tailscale_state` is a named volume holding the node's identity and keys,
so restarting the container reconnects as the same tailnet device instead
of registering as a new one on every restart.

---

## Bugsink stays private

`bugsink` (self-hosted error monitoring) binds to `127.0.0.1:8211` only, not
Funnel: `docker/tailscale-serve-config.json` proxies `frontend:80` alone.
Reach Bugsink over your tailnet directly (Tailscale gives every device on
the tailnet access without Funnel), or at `http://localhost:8211` on the
host itself.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `tailscale` container exits immediately | `TS_AUTHKEY` is missing, expired, already consumed, or not reusable. | Generate a new reusable auth key in the Tailscale admin console, set `TS_AUTHKEY`, then recreate the `tailscale` service. |
| Machine appears in Tailscale but public URL does not resolve | DNS and certificate registration have not finished, or MagicDNS/HTTPS Certificates/Funnel is disabled. | Wait a few minutes, then verify MagicDNS, HTTPS Certificates, and Funnel are enabled in the admin console. |
| `.ts.net` names do not resolve on your device | Local DNS resolver is not using the Tailscale DNS configuration correctly. | In the Tailscale admin console DNS settings, add global nameservers such as `8.8.8.8`, `8.8.4.4`, `1.1.1.1`, or `1.0.0.1`, then enable the override option if that matches your tailnet policy. Disconnect and reconnect the affected client. |
| Public URL loads a TLS or certificate error | HTTPS Certificates are disabled or the certificate has not been provisioned yet. | Enable HTTPS Certificates under Tailscale DNS settings and wait for provisioning. |
| Public URL resolves but returns no app | `docker/tailscale-serve-config.json` is not loaded or `frontend` is unhealthy. | Check `docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml -f docker/app/compose/docker-compose.local-prod-tailscale.yml --env-file env/mystic_auth/.env.local-prod-tailscale --env-file env/app/.env.local-prod-tailscale logs tailscale frontend backend`. |
| Google login returns `redirect_uri_mismatch` | Google Cloud Console callback does not match `GOOGLE_REDIRECT_URI`. | Register `https://mystic-auth.<tailnet>.ts.net/auth/oauth2/callback/google` exactly. |
| Bugsink is not public | This is expected. Funnel exposes `frontend:80` only. | Use `http://localhost:8211` on the host or access Bugsink privately over the tailnet. |

---
