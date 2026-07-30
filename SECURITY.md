# Security Policy

## Supported versions

There is one line of development, `main`. Security fixes land there.

## Reporting a vulnerability

**Please do not open a public GitHub Issue for a security vulnerability.**
Report it privately to the repository owner instead, including:

- What the vulnerability is and where it lives (file/route/component).
- Steps to reproduce, or a proof-of-concept if you have one.
- The impact as you understand it.

For the inherited mystic_auth foundation specifically, upstream also accepts
reports via [GitHub's private vulnerability reporting](https://github.com/Nachiket-2024/mystic-auth/security/advisories/new).

## Scope

This project's own code (`backend/app/`, `frontend/src/app/`) is in scope:
in particular, the company-hierarchy access-control model described in
[`docs/app/access-control/`](docs/app/access-control/README.md): if you can see
or modify a company/balance sheet outside the scope your assigned policy
grants, that's a real finding.

The inherited authentication/PBAC/audit-logging foundation
(`backend/mystic_auth/`, `frontend/src/mystic_auth/`) follows
[mystic-auth's own security policy](https://github.com/Nachiket-2024/mystic-auth/blob/main/SECURITY.md);
see [`docs/mystic_auth/security/`](docs/mystic_auth/security/) for what's
already been deliberately considered there.

**Out of scope**: vulnerabilities in third-party dependencies (report those
upstream to the dependency's own maintainers; this repo scans for known
dependency CVEs on every push/PR via `pip-audit`/`npm audit` in CI), and the
Groq API itself (report those to Groq).

Not every limitation is a vulnerability to report: some are deliberate,
documented scope boundaries. See
[Known Issues, Limitations & Technical Debt](docs/mystic_auth/concerns/README.md)
for the running list of what's already known and why it's not (yet, or ever)
fixed.
