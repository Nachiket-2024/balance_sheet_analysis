# Balance Sheet Analysis App Docs
---
This is a balance-sheet analysis tool for company analysts and
top-management, built on the [mystic-auth](https://github.com/Nachiket-2024/mystic-auth)
template for authentication and Policy-Based Access Control (PBAC). See
[`../mystic_auth/README.md`](../mystic_auth/README.md) for what the template
itself provides (login, PBAC, audit logging, Docker, CI/CD). This directory
only documents what this project adds on top of it.

`docs/mystic_auth/` holds the template reference docs for architecture,
authentication, authorization, and infrastructure. Treat that folder as
upstream-owned so future `scripts/mystic_auth/upstream-sync/sync-upstream.sh` runs can merge cleanly.
Anything about your product, domains, or decisions belongs in this folder.

> Diagram omitted. See the surrounding prose, tables, or numbered steps for the same flow.

---

## Pages

---

- **[Application Quickstart](quickstart.md)**: start the app, create an administrator, seed app policies, and grant a user access.
- **[Application flows](flows/README.md)**: Mermaid diagrams for the app’s main user and background-job flows.
- **[architecture/](architecture/README.md)**: feature-folder layout, the `app/`
  vs `mystic_auth/` split in practice, why it's structured the way it is, and
  how this app's own UI text/error codes are translated into mystic_auth's
  four supported languages ([architecture/translations.md](architecture/translations.md)).
- **[features.md](features.md)**: implementation notes for deterministic
  analysis, balance-sheet and statement imports, alerts, saved reviews, and
  grounded LLM chat.
- **[access-control/](access-control/README.md)**: the company-hierarchy access
  model (a CEO sees only their company, a group executive sees their whole
  group), and how it's built on top of mystic-auth's PBAC.
- **[api.md](api.md)**: this app's company, financial data, analysis, review,
  and LLM endpoints; MysticAuth's own endpoints are documented in
  [`../mystic_auth/`](../mystic_auth/README.md).
- **[setup.md](setup.md)**: environment variables this app adds, running
  migrations, and seeding demo data.
- **[syncing.md](syncing.md)**: how `mystic_auth/` itself gets updated from
  upstream.
- **[scripts.md](scripts.md)**: what each helper under `scripts/` does and
  when you'd run it.

---

## See also

---

- [Application Quickstart](quickstart.md)
- [Application flows](flows/README.md)
- [Architecture](architecture/README.md)
- [Access control](access-control/README.md)
