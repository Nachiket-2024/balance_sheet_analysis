# Contributing
---
Contributions should keep this application's product code, documentation, and
deployment configuration in the downstream-owned paths. MysticAuth is the
upstream authentication and PBAC template; preserve its ownership boundary
when making changes. See the
[template ownership guide](docs/mystic_auth/template-usage/ownership-split.md).
---

## Before changing code

---

- Check any local `AGENTS.md` instructions in this checkout before editing;
  local instructions can add repository-specific validation requirements.
- Place product behavior in `backend/app/` or `frontend/src/app/`, with tests
  under the matching `tests/**/app/` tree.
- Keep app docs in `docs/app/` and project screenshots in `screenshots/app/`.
- Use the MysticAuth public SDK and documented extension points. Do not hand
  edit upstream-owned files under `backend/mystic_auth/`,
  `frontend/src/mystic_auth/`, or `docs/mystic_auth/`.
- Update comments and docs when behavior, commands, configuration, or API
  contracts change. Keep comments focused on non-obvious decisions.
---

## Local setup

---

Use the [Application Quickstart](docs/app/quickstart.md) to create the paired
environment files, start the Docker Compose stack, create an administrator,
and grant app access. The root [README](README.md#quickstart) gives the short
startup path.
---

## Validation

---

Run the checks relevant to your change. For application changes, the full CI
pipeline is the release gate; it includes backend lint, type checking,
migrations, tests, security checks, frontend checks and coverage, secrets
scanning, tooling regressions, Docker validation, and browser E2E. See
[CI/CD Overview](docs/mystic_auth/cicd/overview.md#local-equivalents) for
commands and [Testing Overview](docs/mystic_auth/testing/overview.md) for the
test suites.

For documentation changes, check local links, anchors, code examples, Mermaid
diagrams, heading separators, and the MysticAuth ownership boundary. Do not
change upstream-owned docs to make an app-specific statement fit.
---

## Pull requests

---

Keep a pull request focused, explain the reason for the change, and report the
checks you ran. Include screenshots when a UI change affects the product
screenshots in the README.
---

See [Security](SECURITY.md) for private vulnerability reporting and the
[License](LICENSE) for contribution terms.
