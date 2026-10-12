# Glossary
---

Plain-language definitions for terms that show up across this documentation. If you're new to the codebase, skim the pages below once, then use them as a lookup while you read the flow docs. Split by topic so no single page gets unwieldy; each term links back to its own page and heading (e.g. `glossary/authentication.md#jwt`) for exactly this reason.

1. [Authentication & Sessions](authentication.md): tokens, cookies, login defenses, account lifecycle (JWT, PKCE, CSRF, refresh-token rotation, chain id, brute-force lockout, soft delete, XSS, and more)
2. [Authorization (PBAC)](authorization.md): policies, permissions, and access-decision terms (PBAC, role-based access control, condition handlers, policy history, privilege escalation guard, granular permissions, and more)
3. [Infrastructure](infrastructure.md): database, backend framework, background jobs, deployment, HTTP security, and CI/CD terms (Postgres, Valkey, Alembic, FastAPI, Docker Compose, Caddy, Cloudflare/ngrok/Tailscale tunnels, CORS, CSP, and more)
4. [Frontend](frontend.md): frontend libraries and UI patterns (shadcn/ui, Radix UI, Tailwind CSS, Zustand, TanStack Query, Axios, command palette, gate components, lazy routes)
5. [Operations](operations.md): error monitoring, geolocation, and localization terms (Bugsink, MaxMind GeoLite2, PII, i18n)
6. [Testing](testing.md): test-suite and tooling terms (unit, integration, security, and performance suites, mocks, fixtures, coverage gate, pytest, Vitest)
7. [Local Scripts & Dev Tooling](tooling.md): the helper scripts that wrap day-to-day setup (dev-up helper, backend-exec helper, system-user bootstrap script, env files)

---
