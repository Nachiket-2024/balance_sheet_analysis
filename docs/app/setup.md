# Setup

Follow mystic-auth's own setup first:
[`../mystic_auth/README.md`](../mystic_auth/README.md) and
[`template-usage/overview.md`](../mystic_auth/template-usage/overview.md), to get
`docker compose up` running with a system superuser created. Everything
below is additional, specific to this app.

## Environment variables this app adds

Not part of `mystic_auth.core.settings.Settings` (that's a template
internal); loaded independently by `backend/app/llm/llm_config.py` from the
same root `.env`:

| Variable        | Required | Default                                              |
|------------------|----------|--------------------------------------------------------|
| `GROQ_API_KEY`    | Yes (for LLM chat) | none: chat requests fail with 502 until set |
| `GROQ_API_URL`    | No       | `https://api.groq.com/openai/v1/chat/completions`        |
| `GROQ_MODEL`      | No       | `llama-3.1-8b-instant`                                    |

Documented (and prefillable) in the root [`.env.example`](../../.env.example),
under its own "This app's own domain config" section, separate from
mystic-auth's own template variables above it.

## Migrations

This app's tables (`companies`, `balance_sheets`) share mystic-auth's own
alembic history: one `alembic upgrade head` (via `docker compose run --rm
alembic`, or the `alembic` service that runs automatically on `docker compose
up`) applies both. See `backend/alembic/env.py` for how both sets of models
feed into the same `target_metadata`.

## Baseline policies (automatic)

`docker compose up` also runs the `seed-base-policies` service once,
automatically, right after migrations (same one-shot pattern as the
`alembic` service): creates this app's two ready-to-assign RBAC-shaped
policies, `role_company_viewer` and `role_company_manager` (see
`backend/app/seed/seed_base_policies.py` and
[Baseline Policies](access-control/baseline-policies.md)).
Nothing to run by hand: after creating the system superuser above, assign
one of these two policies to a user from the `/policies` UI and they can
use the app immediately, with no conditions JSON to write. Idempotent, so it's
a no-op on every subsequent `docker compose up`.

## Seeding demo data (optional)

To additionally explore the full company-hierarchy *scoping* model (not
just the two unconditioned roles above), seed a demo Reliance-group dataset
(three companies, three users: an analyst, a company CEO, and a group
executive, each with the company-scoped policy [Access Control](access-control/overview.md)
describes):

```bash
docker compose exec backend python -m app.seed.seed_demo_data
```

You'll be prompted for a password to use for all three demo accounts
(`analyst@example.com`, `ceo.jio@example.com`, `ambani@example.com`). Safe to
re-run: it skips any company/user/policy that already exists. Unlike
`seed-base-policies`, this is a disposable fixture, not something that runs
automatically, so delete the companies it creates (cascades to their balance
sheets and policy assignments) when you're done exploring it.
