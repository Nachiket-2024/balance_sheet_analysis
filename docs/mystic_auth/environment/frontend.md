# Environment Configuration: Frontend Build Settings
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

These are read through `import.meta.env` in the browser code. In production
style Docker modes they are baked into the static bundle during
`docker/mystic_auth/dockerfiles/frontend.Dockerfile`'s `builder` stage. Changing one means
rebuilding the frontend image.

| Variable | Reader | Actual use |
|---|---|---|
| `VITE_API_BASE_URL` | `frontend/src/mystic_auth/core/settings.ts` | Axios base URL, OAuth login button URL, and SSE session-events URL. Empty means same-origin API calls through nginx. |
| `VITE_APP_NAME` | `frontend/src/mystic_auth/core/settings.ts` | Product name shown in the UI and document title. Compose aliases it from `APP_NAME`. |
| `VITE_APP_LOGO_URL` | `frontend/src/mystic_auth/core/settings.ts` | Optional image `src` for `Logo.tsx` in the sidebar and auth layout. Not aliased from a backend variable. |
| `VITE_APP_FAVICON_URL` | `frontend/src/mystic_auth/core/settings.ts` | Optional browser tab favicon, applied in `theme/applyFaviconAndMetaColor.ts`. Overrides the generated brand-color icon so a signed-in user's Appearance pick can't replace a deployment's fixed favicon. Not derived from `VITE_APP_LOGO_URL`. Not aliased from a backend variable. |
| `VITE_SUPPORT_EMAIL` | `frontend/src/mystic_auth/core/settings.ts` | Legal/contact display and optional sidebar support link. Compose aliases it from `SUPPORT_EMAIL`. |
| `VITE_BRAND_COLOR` | `frontend/src/mystic_auth/core/settings.ts` | App-wide default brand color. Empty falls back to the shipped terracotta `#b5533c`. Compose aliases it from `BRAND_COLOR`. |
| `VITE_SENTRY_DSN` | `frontend/src/mystic_auth/core/errorMonitoring.ts` | Browser error-monitoring DSN. Empty disables frontend error monitoring. |
| `VITE_SENTRY_ENVIRONMENT` | `frontend/src/mystic_auth/core/errorMonitoring.ts` | Browser error-monitoring environment tag. Empty falls back to Vite's `MODE`. |

---

See [Environment Configuration](README.md) for the full index.

---
