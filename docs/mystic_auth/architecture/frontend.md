# Frontend Architecture

## Purpose

React 19 + TypeScript SPA (`frontend/src/mystic_auth/`, with the entry point and extension surface, namely `main.tsx`, `App.tsx`, `sdk.ts`, `app_sdk.ts`, in the sibling `frontend/src/app/`; see [Using This Repository as a Template](../template-usage/overview.md#the-app--mystic_auth-split)), built with Vite, styled with Chakra UI v3. Feature-organized to mirror the backend's domain split, with a PBAC-aware UI layer that mirrors the backend's permission vocabulary.

## Module layout

| Module | Purpose |
|---|---|
| `auth/` | Login, signup, logout, logout-all, OAuth2, password reset (request/confirm), account verification, current-user session query, the auth-refresh interceptor; each sub-feature is its own folder (Page/Form/mutation-hook/types); `password_rules/` holds password-complexity validation (`passwordRules.ts`) and its checklist UI, shared by signup/reset/profile |
| `authorization/` | The PBAC layer: `permissions.ts` (frontend mirror of the backend `Permission` enum), `authorizationService.ts` (batch permission-check calls, policy/audit-log fetches), `useAuthorization`/`useCan` (`useAuthorized` is a same-hook alias for call sites that read more naturally as "is the caller authorized" than "can the caller"), and the gate components `Authorized`, `IfCan`, `ProtectedRoute` |
| `audit_log/` | `AuditLogPage.tsx`: the caller's own PBAC audit trail, plus an "all users" tab for privileged callers |
| `dashboard/` | Landing page after login |
| `policies/` | Admin CRUD UI for PBAC policies |
| `profile/` | Self-service profile view/update, plus `useUnsavedChangesWarning` (its only consumer) |
| `users/` | Admin user management (list, mutate, assign policies) |
| `api/` | Axios-based typed call functions per backend domain (`auth_api`, `users_api`, `profile_api`, `policies_api`, `audit_api`), plus `axiosInstance.ts` and `apiError.ts` |
| `store/` | Zustand: `authStore.ts` (session/profile/permissions), `themeStore.ts` (light/dark); client state only, no Redux |
| `core/` | App-wide settings (`APP_NAME`, `VITE_API_BASE_URL`), `queryClient.ts` (the shared TanStack Query client), and `errorMonitoring.ts` (a no-op unless `VITE_SENTRY_DSN` is set, which the default self-hosted Bugsink service sets automatically, see [Error Monitoring](../error-monitoring/overview.md)) |
| `layout/` | App shell: `AppLayout`, `Navbar`, `Sidebar`, `ThemeToggle`, `navItems.ts`. `AppLayout` takes an optional `extraNavItems: NavItem[]` prop so your own feature routes can add sidebar links without editing `navItems.ts` (upstream-owned). See [Using This Repository as a Template: shared-chrome extension points](../template-usage/overview.md#shared-chrome-extension-points) |
| `ui/` | Generic reusable UI kit, no feature ownership: `DataTable`, `ConfirmDialog`, `FormAlert`, `PageContainer`, `Card`, `LoadingState`, `toaster`/`toasterInstance`, `ErrorBoundary` |
| `theme/` | `system.ts`: Chakra UI v3 design tokens |
| `sdk.ts` | Public extension surface for your own feature code: the intended single import point for anything you build on top of this template, rather than reaching into the internal modules above directly. Groups roughly into: **PBAC** (`PERMISSIONS`, `useAuthorization`, `useCan`/`useAuthorized`, `Authorized`, `IfCan`, `ProtectedRoute`, `authorizationService`), **API/session** (`api`, `extractApiErrorMessage`, `useAuthStore`, `queryClient`, `settings`/`APP_NAME`, `reportError`), **app shell** (`AppLayout`, `NavItem`, `Toaster`, `toaster`), and **generic UI primitives** (`LoadingState`, `Card`, `PageContainer`, `DataTable`/`DataTableColumn`, `ConfirmDialog`, `FormAlert`, `ErrorBoundary`). See [Using This Repository as a Template: the app/ + mystic_auth split](../template-usage/overview.md#the-app--mystic_auth-split) |

This layout deliberately mirrors the backend's own domain split (`backend/mystic_auth/auth/`, `backend/mystic_auth/authorization/`, `backend/mystic_auth/core/`, etc.) rather than a layer-first (`components/`/`hooks`/`services`) MVC structure: a file's folder tells you which backend domain it serves, not what kind of file it is. `api/`, `store/`, `core/`, `layout/`, `ui/`, and `theme/` are the exceptions: infrastructure/cross-cutting concerns with no single feature owner, kept as their own top-level folders rather than scattered into every feature that touches them.

## State management

- **Zustand** for client state: `store/authStore.ts` (`isAuthenticated`, `name`, `email`, `role`, `permissions`, `hasPassword`) and `store/themeStore.ts` (light/dark). No Redux.
- **TanStack Query** for all server state/caching, via one shared `QueryClient` (`core/queryClient.ts`).
- `authStore.isAuthenticated` starts as `null` ("not checked yet"), so `App.tsx` blocks rendering the router behind a loading screen until `useAuthSession()` resolves it to `true`/`false`, avoiding a flash of unauthenticated content.

## API layer

`api/axiosInstance.ts` is a single Axios instance, `withCredentials: true` (cookie-based session; the JWT itself is never stored in JS-accessible state, see [Authentication Overview](../authentication/overview.md#tokens-and-cookies)), base URL from `VITE_API_BASE_URL`. Per-domain typed call functions live in `api/*.ts` (`auth_api`, `users_api`, `profile_api`, `policies_api`, `audit_api`); `api/apiError.ts` shapes error responses uniformly. `users_api.ts` (admin user management) and `profile_api.ts` (self-service `PUT /users/me`) are separate modules, since they have different callers and different permission requirements, even though both ultimately hit the backend's single `user_routes.py`.

`auth/setupAuthInterceptor.ts` implements silent-refresh-on-401: a single in-flight refresh call is shared across concurrently-failing requests (no thundering herd of refresh calls), and login/signup/refresh/logout/reset/verify/oauth2 endpoints are excluded from the retry-after-refresh logic to avoid infinite loops. On an unrecoverable 401, it marks `authStore` unauthenticated and clears the cached `GET /auth/me` query. It does not handle `403`; permission failures are left entirely to route/component-level guards (`ProtectedRoute`, `Authorized`, `IfCan`). It lives under `auth/`, not `api/`, since it's auth-session business logic that happens to configure the shared Axios instance, not a typed API call itself.

## Routing

`react-router` v8 (see [below](#why-react-router-not-react-router-dom) for why not `react-router-dom`), `BrowserRouter`, defined in `App.tsx`. Only `LoginPage` is eager-loaded (the most common unauthenticated entry point); every other route is `React.lazy`-split.

### Why `react-router`, not `react-router-dom`

Upstream stopped publishing `react-router-dom` past `7.18.1` and folded its exports into `react-router` for v8: everything except the RSC-only `RouterProvider`/`HydratedRouter` (under `react-router/dom`, unused here) now comes from the single `react-router` package. Not optional: `react-router-dom@7.18.1` carried an unpatched high-severity advisory ([GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)) with no further release ever published under that package name. The fix only exists as `react-router@8.3.0`.

| Route | Access | Notes |
|---|---|---|
| `/`, `/dashboard` | authenticated | `DashboardPage` |
| `/users` | `USERS_LIST_ALL` | Admin user management |
| `/policies` | `POLICIES_READ` | PBAC policy admin |
| `/audit-log` | authenticated (self-service) | "All users" tab gated separately inside the page |
| `/profile` | authenticated | |
| `/login`, `/signup`, `/verify-account`, `/password-reset-request`, `/reset-password` | public | |
| `/not-authorized` | public | 403 landing, where `ProtectedRoute` sends an authenticated-but-unauthorized user |
| `*` | public | 404 |

All protected routes are wrapped in `ProtectedRoute` (redirects unauthenticated → `/login`, unauthorized → `/not-authorized`) and `AppLayout` (sidebar/top-bar shell), so the shell only renders once access is actually confirmed.

## Authorization on the frontend (PBAC-aware UI)

- `authorization/permissions.ts` mirrors the backend's `Permission` enum as string constants, so route/component gates reference `PERMISSIONS.USERS_LIST_ALL` rather than a hand-typed string.
- `authorization/useAuthorization.ts` reads `authStore.permissions` and exposes `can(action)`, failing closed (`false`) when unauthenticated or still loading. This is a **client-side UX convenience only**: the backend independently enforces every action via `require_authorization` (see [PBAC Architecture](../authorization/architecture.md)); a hidden button is not a security boundary.
- `authorization/ProtectedRoute.tsx`, `Authorized.tsx`, `IfCan.tsx`: route-level and in-page conditional gates built on `useAuthorization`.
- `authorization/authorizationService.ts` layers real per-resource/conditional checks (`POST /authorization/batch-check`) on top of the cached flat permission list for cases that need it.
- `role` is explicitly treated as metadata only on the frontend too, never used in a gating decision, mirroring the backend's own design (see [Security Decisions: role is never used to decide access](../security/decisions.md#role-is-never-used-to-decide-access)).

## Theming

Chakra UI v3 (`@chakra-ui/react` + Emotion). `theme/system.ts` defines the design tokens; `store/themeStore.ts` + `layout/ThemeToggle.tsx` handle light/dark switching, independent of the OS-level `prefers-color-scheme`.

## Build & bundling

`vite.config.ts` uses Rollup's default automatic chunking, not `build.rollupOptions.output.manualChunks`. A prior version manually split every `node_modules` import into one `vendor` chunk (for better long-term browser-cache reuse: a deploy that only touches app code wouldn't have busted the cache for third-party code that hadn't changed). That was reverted after it broke production: app code like `api/axiosInstance.ts` both imports from and gets imported by the vendor chunk, and Rollup placed shared CJS-interop helpers into `axiosInstance`'s own chunk, creating a real circular chunk dependency. ESM's live-binding semantics for circular imports meant `vendor.js` called a binding from `axiosInstance.js`'s chunk before that chunk's module body had run far enough to define it, throwing `"TypeError: t is not a function"` at the very top of the vendor bundle: the whole app failed to mount, a blank page with no build-time warning. See the comment in `vite.config.ts` for the full account. Re-introducing manual chunking is possible later, but only with real production verification (not just a local build) that nothing crashes.

The build still trips Vite's "chunk larger than 500 kB" warning on the main entry chunk. The bulk of it is Chakra UI v3's `defaultConfig` (imported by `theme/system.ts`, required at the app root by `ChakraProvider`): it's one object bundling style recipes for *every* built-in Chakra component, including several this app never renders (Menu, Combobox, TreeView, TagsInput, NumberInput, ColorPicker). Rollup can tree-shake unused *modules* but not unused *properties* of an object that's genuinely referenced, so their `@zag-js/*` machine code (~150 kB+ unminified) comes along regardless. There's no supported way to hand-pick a subset of Chakra's default recipes without forking the theme system, so this is treated as a justified, inherent cost of the library choice rather than something to chase; `build.chunkSizeWarningLimit` is deliberately left untouched so the warning stays visible instead of being silenced.

Route-level code splitting is separate and already in place. See [Routing](#routing) above: every route except `LoginPage` is `React.lazy`-loaded, so route chunks only ever contain that page's own code plus the Chakra sub-components it specifically imports.

## Configuration requirements

`VITE_API_BASE_URL` (the backend's base URL) and `VITE_APP_NAME` (the product name shown in the UI: navbar, auth pages, document title via `index.html`'s `%VITE_APP_NAME%` substitution). Both are Vite build-time env vars, read through `core/settings.ts`, and set in the root `.env`; running the stack via Docker, that's what the frontend container actually reads. `frontend/.env.example` only matters for running the frontend locally with `npm run dev`, outside Docker. Support email shown in emails is backend-driven (`SUPPORT_EMAIL`) and only ever appears in server-rendered email templates, not in the frontend build.

## Edge cases / error handling

- A 401 mid-session (expired access token) triggers one silent refresh-and-retry; a second failure marks the session invalid and, per route, redirects to `/login`.
- A 403 (authorization denial) is a normal API response the calling component/page is responsible for handling: typically a toast or an inline `FormAlert`, not a global redirect (except at the route level via `ProtectedRoute`).
- An uncaught render-time error anywhere in the tree (a bad API response shape reaching a component that doesn't expect it, a null-pointer bug, etc.) is caught by `ui/ErrorBoundary.tsx`, mounted once at the app root in `main.tsx` (outside the router, so it also catches an error thrown before routing itself renders). Shows a "Something went wrong" fallback with a full-page reload action instead of React unmounting the entire tree to a blank white screen. Always logs to the console; also reports to `core/errorMonitoring.ts` (a no-op unless `VITE_SENTRY_DSN` is set, see [Error Monitoring](../error-monitoring/overview.md)).

## Testing coverage

Tests live in `tests/frontend/` (outside `src/`), not co-located. Vitest + React Testing Library + jsdom + axios-mock-adapter. See [Testing Overview](../testing/overview.md) for the full breakdown and known coverage gaps.
