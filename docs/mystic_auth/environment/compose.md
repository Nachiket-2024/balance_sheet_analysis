# Environment Configuration: Compose-Only Settings
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

These values are not `Settings` fields. They are read by Docker Compose,
container entrypoints, one-shot seed commands, or local helper scripts.

| Variable | Modes | Actual use |
|---|---|---|
| `APP_DB_PASSWORD` | all env examples | Read by Alembic migration `b1e6a9f3c7d2_add_least_privilege_app_role.py` to create or update the least-privilege app role used by `APP_DATABASE_URL`. |
| `VALKEY_PASSWORD` | all env examples | Required by production-shaped Compose modes and passed to `valkey-server --requirepass`; `setup-env` embeds the same generated value in `VALKEY_URL`. See [Valkey authentication](../security/hardening-infra.md#valkey-authentication). |
| `BUGSINK_SECRET_KEY` | all env examples | Django secret key for Bugsink. Must be a real long value or Bugsink fails its deploy checks and crash-loops. |
| `BUGSINK_SUPERUSER_EMAIL` | all env examples | Bugsink admin username/email and the switch that lets the backend watch for a late seeded DSN in dev/local stacks. |
| `BUGSINK_SUPERUSER_PASSWORD` | all env examples | Bugsink admin password. |
| `BUGSINK_BASE_URL` | all env examples | Internal or public Bugsink base URL, depending on mode. |
| `GEOIPUPDATE_ACCOUNT_ID` | dev, local-prod, and prod | MaxMind account id used by the optional `geoipupdate` service. Requires `--profile geoip`; the dev wrapper adds that profile when `GEOIP_DB_PATH` is set. |
| `GEOIPUPDATE_LICENSE_KEY` | dev, local-prod, and prod | MaxMind license key used by the optional `geoipupdate` service. Requires `--profile geoip`; the dev wrapper adds that profile when `GEOIP_DB_PATH` is set. |
| `BACKUP_INTERVAL_HOURS` | local-prod and prod | Sleep interval for the always-on `db_backup` sidecar. Defaults to `24` if Compose substitution gets an empty value. |
| `BACKUP_RETENTION_DAYS` | local-prod and prod | Local dump retention for the `db_backup` sidecar. Defaults to `14` if Compose substitution gets an empty value. |
| `TUNNEL_TOKEN` | local-prod Cloudflare named tunnel | Cloudflare Tunnel token consumed by the `cloudflared` container. Not needed for Cloudflare Quick Tunnel. |
| `NGROK_AUTHTOKEN` | local-prod ngrok | ngrok account auth token consumed by the `ngrok` container. |
| `NGROK_DOMAIN` | local-prod ngrok | Static ngrok domain used by the tunnel command and public base URLs. |
| `TS_AUTHKEY` | local-prod Tailscale | Tailscale auth key consumed by the `tailscale` container. |
| `TS_HOSTNAME` | local-prod Tailscale | Tailscale machine name used by the Funnel setup. |
| `PUBLIC_DOMAIN` | prod | Public app domain used by Caddy routing. |
| `ACME_EMAIL` | prod | Email address Caddy passes to Let's Encrypt for certificate management. |
| `BUGSINK_PUBLIC_DOMAIN` | prod | Public Bugsink domain used by Caddy routing and public frontend DSN planning. |

---

See [Environment Configuration](README.md) for the full index.

---
