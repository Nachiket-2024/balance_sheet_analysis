# Session Geolocation
---

*New to a term here? See the [Operations Glossary](../glossary/operations.md).*

Off by default. Resolves each login's city/country from its IP for the "Manage Sessions" dashboard's Location column, so a user with the required permission can tell "Sydney, Australia" from "an unfamiliar location" at a glance, rather than staring at a bare IP address.

---

## How it works

`backend/mystic_auth/user_session/session_geolocation.py` resolves the lookup from a local **MaxMind GeoLite2-City** database (`geoip2` library reading a `.mmdb` file), not a third-party HTTP API: the lookup is offline and sub-millisecond, so it adds no latency, no rate limit, and no external outage dependency to the login/refresh path.

Leaving `GEOIP_DB_PATH` empty (the default) disables the feature entirely: `resolve_city_country` returns `(None, None)` for every lookup, and the Location column shows "Unknown", the same fail-open posture as every other best-effort field on `UserSession` (see `session_service.py`). Nothing else in the app depends on it.

For local development, leave `GEOIP_DB_PATH` empty unless you have downloaded
the database yourself. Setting it to `/usr/share/GeoIP/GeoLite2-City.mmdb`
without provisioning that file intentionally makes `/health/ready` return 503;
this prevents a deployment that requested GeoIP from being reported ready while
the feature is unavailable. Use the `geoip` Compose profile and its updater, or
clear the setting when GeoIP is not needed.

---

## Enabling it under Docker

Every Compose mode, including dev, ships an optional `geoipupdate` service (MaxMind's own official updater, not a hand-rolled cron script) that downloads `GeoLite2-City.mmdb` into a `geoip_data` volume also mounted read-only into `backend`, and keeps re-checking for a new database on its own schedule (`GEOIPUPDATE_FREQUENCY`, in hours) for as long as the container runs. The file never goes stale without anyone having to remember to refresh it by hand.

It's gated behind the `geoip` Compose profile, so it never starts (and never restart-loops on missing credentials) unless explicitly enabled:

---

1. Create a free MaxMind account: <https://www.maxmind.com/en/geolite2/signup> (email + password, no payment info, no trial period; GeoLite2 is free). Verify your email via the link MaxMind sends before the account is usable.

---

2. Log in at <https://www.maxmind.com/en/account/login>. The account dashboard shows a numeric **Account ID**, that's `GEOIPUPDATE_ACCOUNT_ID`.

---

3. In the left sidebar, go to **Manage License Keys** → **Generate new license key**. When it asks whether the key is for use with `geoipupdate`, say yes (this changes the key's format/permissions to match). Copy the key immediately: MaxMind only shows it once. That's `GEOIPUPDATE_LICENSE_KEY`.

---

4. In the active `env/mystic_auth/.env.dev`, `.env.local-prod-*`, or `.env.prod` file, set `GEOIPUPDATE_ACCOUNT_ID` and `GEOIPUPDATE_LICENSE_KEY` to those two values, and set `GEOIP_DB_PATH=/usr/share/GeoIP/GeoLite2-City.mmdb` (the path `geoipupdate` writes to inside the shared volume). The dev example declares all three fields empty by default, so GeoIP remains disabled until you opt in with valid credentials.

---

5. Start (or restart) the stack **with the profile enabled**. This is the step it's easy to miss, since nothing about steps 1-4 warns you it's still required:

   ```bash
   docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml -f docker/app/compose/docker-compose.prod.yml --env-file env/mystic_auth/.env.prod --env-file env/app/.env.prod --profile geoip up -d --build
   ```

   (swap in your tunnel's `docker-compose.local-prod-*.yml` and matching `env/mystic_auth/.env.local-prod-*` for local-prod). For dev, use the normal dev Compose files and add `--profile geoip`; `dev-up.sh`/`.ps1` adds that profile automatically when `GEOIP_DB_PATH` is non-empty and fails early if either updater credential is missing. Without the profile, `geoipupdate` is skipped entirely and `backend` mounts an empty volume, so a configured path makes readiness fail until the profile is enabled.

---

6. `geoipupdate` needs one successful run before the file exists. Its Compose healthcheck now requires a non-empty `GeoLite2-City.mmdb`; while the first download is pending it is `starting`, and invalid credentials, network failure, or a missing file make it `unhealthy` instead of reporting a false healthy state. Check both the service health and the mounted file:

   ```bash
   docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml -f docker/app/compose/docker-compose.local-prod-ngrok.yml --env-file env/mystic_auth/.env.local-prod-ngrok --env-file env/app/.env.local-prod-ngrok exec geoipupdate ls -la /usr/share/GeoIP/
   ```

   and expect a non-empty `GeoLite2-City.mmdb`. Also inspect the health state:

   ```bash
   docker inspect --format '{{.State.Health.Status}}' mystic-auth-local-prod-ngrok-geoipupdate-1
   ```

   The backend still fails open for the user-facing session-location field and shows "Unknown" until the file is usable. If `backend` was already running when the file appeared, restart it: the GeoIP reader is cached after its first open attempt and is not retried on every request:

   ```bash
   docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml -f docker/app/compose/docker-compose.local-prod-ngrok.yml --env-file env/mystic_auth/.env.local-prod-ngrok --env-file env/app/.env.local-prod-ngrok restart backend
   ```

   If the updater remains `unhealthy`, check `docker compose logs geoipupdate` and confirm the account ID/license key are valid for the `geoipupdate` edition. Do not mark the deployment ready while the profile is enabled but this service is unhealthy.

See [Docker Overview: services](../docker/overview.md#services) for where `geoipupdate` fits among the rest of the stack, and the deployment walkthroughs ([Prod](../deployment/prod.md), and local-prod's [Quick Tunnel](../deployment/local-prod/cloudflare-quick-tunnel.md), [Named Tunnel](../deployment/local-prod/cloudflare-named-tunnel.md), [ngrok](../deployment/local-prod/ngrok-tunnel.md), [Tailscale Funnel](../deployment/local-prod/tailscale-funnel.md)) for this as a step in context.

---

## Enabling it outside Docker

1. Create a MaxMind account and license key the same way as steps 1-3 above.
2. Download `GeoLite2-City.mmdb` yourself (MaxMind's license does not permit redistributing the file itself, so it can't ship in this repo), and set `GEOIP_DB_PATH` to that file's path.
3. Keep it current yourself. MaxMind publishes updates roughly weekly; run their [`geoipupdate`](https://github.com/maxmind/geoipupdate) CLI tool on a periodic schedule (e.g. a system cron job) rather than the Docker service above.

---

## Security notes

- **The `.mmdb` file itself carries no secrets.** It's a public geo-IP dataset, safe to have on disk unencrypted. What's sensitive is `GEOIPUPDATE_LICENSE_KEY`, which is tied to your MaxMind account: treat it like any other credential in `.env.prod`/`.env.local-prod`, not something to commit or share.
- **Resolution is IP-only, best-effort, and never blocks auth.** A failed or missing lookup degrades to "Unknown," never to a login/refresh failure, see `session_geolocation.py`'s own fail-open handling and the module-level `_get_reader` cache (it logs the "file missing" error once, not on every request, so a fix doesn't show up in Location until the next `backend` restart).
- **Accuracy is inherently approximate.** GeoLite2-City resolves to a city-level estimate from IP allocation data, not a precise location, expect it to be wrong or blank for VPNs, corporate NAT, CGNAT, and some mobile carriers. Don't treat it as an authoritative signal on its own; it's a UX hint for "does this session look familiar," not a security control. (PBAC's `NetworkCondition`, if you use it, gates on the resolved client IP directly, see [Security Hardening: Infrastructure](../security/hardening-infra.md#reverse-proxy-ip-trust), not on this city/country lookup.)

---
