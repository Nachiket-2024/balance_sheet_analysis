# Balance Sheet Analysis App Docs

This is a ChatGPT-style balance-sheet analysis tool for company analysts and
top-management, built on the [mystic-auth](https://github.com/Nachiket-2024/mystic-auth)
template for authentication and Policy-Based Access Control (PBAC). See
[`../mystic_auth/README.md`](../mystic_auth/README.md) for what the template
itself provides (login, PBAC, audit logging, Docker, CI/CD). This directory
only documents what this project adds on top of it.

- **[architecture/](architecture/README.md)**: feature-folder layout, the `app/`
  vs `mystic_auth/` split in practice, and why it's structured the way it is.
- **[features.md](features.md)**: implementation notes for the LLM chat and
  yfinance balance-sheet import.
- **[access-control/](access-control/README.md)**: the company-hierarchy access
  model (a CEO sees only their company, a group executive sees their whole
  group), and how it's built on top of mystic-auth's PBAC.
- **[api.md](api.md)**: this app's own API endpoints (companies, balance
  sheets, LLM chat); mystic-auth's own endpoints (auth, users, policies) are
  documented in [`../mystic_auth/`](../mystic_auth/README.md).
- **[setup.md](setup.md)**: environment variables this app adds, running
  migrations, and seeding demo data.
- **[syncing.md](syncing.md)**: how `mystic_auth/` itself gets updated from
  upstream.
- **[scripts.md](scripts.md)**: what each helper under `scripts/` does and
  when you'd run it.
