# Environment Configuration
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

Every environment variable this repository currently ships in `env/*.example`, grouped by the code
that reads it and split across four pages so each stays a readable size. Use it with the
deployment walkthroughs:

1. Dev: copy both `env/mystic_auth/.env.dev.example` and `env/app/.env.dev.example` to their `.env.dev` counterparts.
1. Local-prod Cloudflare: copy both matching `.env.local-prod-cloudflare.example` files to their runtime names.
1. Local-prod ngrok: copy both matching `.env.local-prod-ngrok.example` files to their runtime names.
1. Local-prod Tailscale: copy both matching `.env.local-prod-tailscale.example` files to their runtime names.
1. Prod: copy both matching `.env.prod.example` files to their runtime names.

`scripts/mystic_auth/env-tools/` has a full set of scripts for all of this: bootstrapping every file at once with fresh generated secrets, keeping a file honest over time, and syncing values from an old file without ever reading its secrets. See [Environment Tooling](tooling.md) for what each one does.

The backend's `Settings` object reads the dev `env/mystic_auth/.env.dev` and
`env/app/.env.dev` files when those values are not already in the process
environment. In local-prod and prod, Compose passes both mode-specific env
files into each service through `env_file:` and both are needed as
`--env-file` inputs for `${VAR}` build-argument substitution.

---

## The `mystic_auth` / `app` split

Every `env/*.example` file above actually comes in a pair, following the
same `mystic_auth`/`app` split used everywhere else in this template (see
[the tiering table](../template-usage/ownership-split.md)):

- `env/mystic_auth/.env.dev<mode-suffix>` - the template's runtime file for fields
  this template defines. The tracked `.example` files are upstream-owned; the
  real `.env` files are local, gitignored deployment state and are expected to
  be edited by the project owner. A sync regenerates/updates the examples, not
  your secrets or deployment values.
- `env/app/.env.dev<mode-suffix>` - yours, ships with the app-owned default
  policy extension point and is where you add your fork's extra variables;
  upstream never edits this file again. App values win
  when the same variable is present in both files.

Both files feed the same running stack: each Compose service lists both in
`env_file:` (mystic_auth's, then app's, so an app-declared value wins on
overlap), and every `docker compose` invocation in this template's own
scripts passes both as `--env-file` too, for `${VAR}` build-argument
substitution. `setup-env.sh` bootstraps both from their `.example` files in
one pass; `check-env.sh` and `set-env-field.sh` check/touch both by default.
See [Docker: Compose Modes](../docker/compose-modes.md#two-files-per-mode-mystic_auth--app)
for the Compose side of this.

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart LR
    MA["env/mystic_auth/.env.dev or .env.<mode>\nupstream-owned"]
    APP["env/app/.env.dev or .env.<mode>\nyours, app-owned settings"]
    SVC["Compose service\nenv_file: [MA, APP]"]
    MA --> SVC
    APP --> SVC
    linkStyle default stroke:#334155,stroke-width:2px
```

---

## Pages

- [Backend Settings](backend.md): template fields read by `backend/mystic_auth/core/settings.py`; app-owned fields are read by `backend/app/core/settings.py`.
- [Frontend Build Settings](frontend.md): `VITE_*` values baked into the static bundle at build time.
- [Compose-Only Settings](compose.md): values read by Docker Compose, entrypoints, or helper scripts, not by the app itself.
- [Environment Tooling](tooling.md): the `scripts/mystic_auth/env-tools/` scripts that set up, maintain, and sync these files for you.

---

## Edge Cases

1. `SECRET_KEY` shorter than 32 characters stops backend startup at settings
  import time.
1. `FRONTEND_ADDITIONAL_BASE_URLS` affects CORS only. It never changes email
  links or OAuth redirects.
1. `TRUSTED_PROXY_IPS` must name the immediate proxy that connects to the
  backend, not the public client IP. If the peer is not trusted, forged
  `X-Forwarded-For` is ignored.
1. Frontend `VITE_*` variables in production-style modes are build-time values.
  Restarting the container is not enough after changing them.
1. `APP_DATABASE_URL` can be blank. When set, the app and Procrastinate task
  bodies use it for CRUD work, while Alembic still uses `DATABASE_URL` for DDL.
1. `GEOIP_DB_PATH` alone does not download a database. Docker downloads the
  MaxMind file only when `geoipupdate` is enabled with `--profile geoip` and
  both `GEOIPUPDATE_ACCOUNT_ID` and `GEOIPUPDATE_LICENSE_KEY` are set. The dev
  wrapper enables the profile automatically when the path is set, but fails
  before startup if either credential is missing.
1. `EMAIL_ENABLED=false` lets flows enqueue and render email content without
  contacting SMTP, but users still need the resulting token/link through logs
  or tests to finish verification or reset flows.
1. `TRUSTED_PROXY_IPS` defaults to empty, so it doesn't need to be present in
  the env file at all. Only the `backend` service needs a real value (the
  prod/local-prod-* Compose files derive and inject it there); `alembic` and
  `procrastinate_worker` read the same env file directly, never use this
  setting, and fall back to the default instead of failing to start.
1. `VALKEY_PASSWORD` is required in production-shaped modes. `setup-env`
  generates it and embeds the same value in `VALKEY_URL`
  (`redis://:<VALKEY_PASSWORD>@valkey:6379/0`), so the server and clients
  cannot silently disagree. See
  [Valkey authentication](../security/hardening-infra.md#valkey-authentication).
1. `tests/backend/mystic_auth/unit/core/test_env_examples_parity_unit.py`
  checks every required `Settings` field against each paired
  `env/mystic_auth/.env*.example` plus `env/app/.env*.example` file, so a field
  that's required but missing from a shipped pair fails CI instead of surfacing
  later as a runtime crash for whoever deploys that mode first. It also guards
  app-owned `DEFAULT_APP_POLICIES` from drifting back into the upstream split.
1. A `<file>.bak` left behind by the sync workflow (see
  [Environment Tooling](tooling.md#what-happens-to-the-bak-files-afterward))
  is never deleted automatically. `check-env/check-env.sh` warns if it
  finds one, but the actual deletion is always a manual, human-confirmed
  step.

---
