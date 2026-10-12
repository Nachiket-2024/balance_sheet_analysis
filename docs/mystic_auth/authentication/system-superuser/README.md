# System Superuser: Bootstrapping and Promotion

---

`backend/mystic_auth/scripts/create_system_user.py` is the only way the reserved system account is ever created or granted; there is no API endpoint for either, by design (see [OAuth2 / PKCE: system account is blocked from OAuth2 login entirely](../oauth2-pkce.md)).

Run it after the stack is started and migrations have completed. Pick the command for the mode you are running.

---

## Non-interactive bootstrap scripts

`local-scripts/mystic_auth/{dev,local-prod-cloudflare,local-prod-ngrok,local-prod-tailscale,prod}/` each hold a `create-system-user.{sh,ps1,bat}` that pipes the fresh-account prompts (email, name, password) into the matching upstream Compose file plus the app-owned Compose override, with both runtime env files loaded. They only cover the fresh-account path below, not promotion of an existing account: run the interactive command further down for that.

To use one:

```bash
cp local-scripts/mystic_auth/dev/system-user.env.example local-scripts/mystic_auth/dev/system-user.env
# edit local-scripts/mystic_auth/dev/system-user.env with real values
local-scripts/mystic_auth/dev/create-system-user.sh        # or .ps1 / .bat
```

Same shape for `local-scripts/mystic_auth/local-prod-{cloudflare,ngrok,tailscale}/` (against the matching `docker-compose.local-prod-*.yml`) and `local-scripts/mystic_auth/prod/` (against `docker-compose.prod.yml`, non-dev credentials). Each `system-user.env` is ignored by both `.gitignore` and `.dockerignore`, only the `.example` templates are tracked, so filling one in never risks committing real credentials.

---

## Command matrix

| Mode | Non-interactive helper | Interactive command | Env file | Compose file |
|---|---|---|---|---|
| Dev Docker | `local-scripts/mystic_auth/dev/create-system-user.sh` / `.ps1` / `.bat` | `docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev exec -it backend python -m mystic_auth.scripts.create_system_user` | `env/mystic_auth/.env.dev` + `env/app/.env.dev` | `docker/mystic_auth/compose/docker-compose.dev.yml` + `docker/app/compose/docker-compose.dev.yml` |
| Local-prod Docker, Cloudflare tunnel | `local-scripts/mystic_auth/local-prod-cloudflare/create-system-user.sh` / `.ps1` / `.bat` | `docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare exec -it backend python -m mystic_auth.scripts.create_system_user` | `env/mystic_auth/.env.local-prod-cloudflare` + `env/app/.env.local-prod-cloudflare` | upstream Compose + `docker/app/compose/docker-compose.local-prod-cloudflare.yml` |
| Local-prod Docker, ngrok tunnel | `local-scripts/mystic_auth/local-prod-ngrok/create-system-user.sh` / `.ps1` / `.bat` | `docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml -f docker/app/compose/docker-compose.local-prod-ngrok.yml --env-file env/mystic_auth/.env.local-prod-ngrok --env-file env/app/.env.local-prod-ngrok exec -it backend python -m mystic_auth.scripts.create_system_user` | `env/mystic_auth/.env.local-prod-ngrok` + `env/app/.env.local-prod-ngrok` | upstream Compose + `docker/app/compose/docker-compose.local-prod-ngrok.yml` |
| Local-prod Docker, Tailscale funnel | `local-scripts/mystic_auth/local-prod-tailscale/create-system-user.sh` / `.ps1` / `.bat` | `docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml -f docker/app/compose/docker-compose.local-prod-tailscale.yml --env-file env/mystic_auth/.env.local-prod-tailscale --env-file env/app/.env.local-prod-tailscale exec -it backend python -m mystic_auth.scripts.create_system_user` | `env/mystic_auth/.env.local-prod-tailscale` + `env/app/.env.local-prod-tailscale` | upstream Compose + `docker/app/compose/docker-compose.local-prod-tailscale.yml` |
| Prod Docker | `local-scripts/mystic_auth/prod/create-system-user.sh` / `.ps1` / `.bat` | `docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml -f docker/app/compose/docker-compose.prod.yml --env-file env/mystic_auth/.env.prod --env-file env/app/.env.prod exec -it backend python -m mystic_auth.scripts.create_system_user` | `env/mystic_auth/.env.prod` + `env/app/.env.prod` | upstream Compose + `docker/app/compose/docker-compose.prod.yml` |
| Local backend without Docker | none | `PYTHONPATH=backend python -m mystic_auth.scripts.create_system_user` | n/a | n/a |

The helper scripts only cover the fresh-account path. If you need to promote an existing account, use the interactive command for that mode.

---

### "Permission denied" running one of these

Git tracks each file's executable bit as part of its mode (`100755` vs `100644`), separate from `chmod` on your local checkout. If the `.sh` was ever added to the repo without `+x` set at the time (e.g. authored with a plain editor rather than `chmod +x` beforehand), git stores it non-executable, and every clone/pull/checkout resets it back to `-rw-r--r--` even after you locally `chmod +x` it and it works once. Fix it in the index, not just on disk, so it stays fixed for everyone:

```bash
git update-index --chmod=+x local-scripts/mystic_auth/dev/create-system-user.sh
```

Repeat per affected file, then commit the mode change. If you're adding a new `.sh` script to this repo, `chmod +x` it before your first `git add` so this never happens in the first place.

---

## Pages

- [Interactive Commands](running-commands.md): the full command for each run mode.
- [Behavior and Prompts](creation-and-promotion-behavior.md): what the script does for a fresh account, an existing password account, and a Google-only account.

---
