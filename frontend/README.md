# Frontend
---

React 19 + TypeScript SPA built with Vite, Tailwind v4 + shadcn/ui (Radix primitives), Zustand, and TanStack Query.

This README stays short on purpose. The full frontend documentation lives under `docs/mystic_auth/`, beside the backend and operations docs, so code folders do not accumulate separate long references.

---

## 1. Source layout
---

| Path | Purpose |
|---|---|
| `frontend/src/mystic_auth/` | Template-owned frontend: auth pages, PBAC gates, dashboard, users, policies, audit logs, settings, layout, UI primitives, translations, theme, API clients, and stores. |
| `frontend/src/app/` | Downstream application extension surface: app routes, app SDK exports, legal/status/landing pages, app theme overrides, and project-owned frontend code. |
| `tests/frontend/mystic_auth/` | Template-owned frontend unit, integration, and browser E2E coverage. |
| `tests/frontend/app/` | Downstream app test area. |

---

## 2. Scripts
---

```bash
npm run dev         # Vite dev server
npm run build        # tsc -b && vite build (production build)
npm run typecheck    # tsc --noEmit across app/node/test tsconfigs
npm run lint         # eslint over frontend/ and tests/frontend/
npm run test          # vitest run (no coverage)
npm run test:coverage # vitest run --coverage (thresholds enforced)
npm run test:browser  # Playwright browser matrix against the running stack
```

Vitest coverage enforces a 90% floor for statements, branches, functions, and
lines. Browser-owned route and layout composition is covered by Playwright;
see the [frontend testing overview](../docs/mystic_auth/testing/overview.md)
for the boundary and the required stack setup.

Browser-only operations such as file downloads are mocked at the jsdom
boundary in Vitest. Their request, filename, and cleanup behavior remain
covered without asking jsdom to navigate to a new document.

---

## 3. Documentation
---

1. [Frontend Architecture](../docs/mystic_auth/architecture/frontend.md)
2. [Implementation Coverage Map](../docs/mystic_auth/architecture/code-map.md)
3. [Frontend Customization](../docs/mystic_auth/template-usage/frontend-customization.md)
4. [Translations Overview](../docs/mystic_auth/translations/overview/README.md)
5. [Appearance](../docs/mystic_auth/appearance/overview.md)
6. [Testing Overview](../docs/mystic_auth/testing/overview.md)

---
