# Documentation

- **[`mystic_auth/`](mystic_auth/README.md):** template reference docs for
  architecture, authentication, authorization (PBAC), database, API reference,
  workers, security, testing, Docker, CI/CD, deployment, and
  [template usage](mystic_auth/template-usage/overview.md). This belongs to
  upstream, so downstream projects should merge updates into it.
- **[`app/`](app/README.md):** the place for product-specific docs in a
  downstream project. It is empty by default.

This mirrors the code split: `backend/mystic_auth/` plus `backend/app/`, and
`frontend/src/mystic_auth/` plus `frontend/src/app/`.
