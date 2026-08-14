# Frontend Architecture

## Purpose

React 19 + TypeScript SPA (`frontend/src/mystic_auth/`, with the entry point and extension surface, namely `main.tsx`, `App.tsx`, `sdk.ts`, `app_sdk.ts`, in the sibling `frontend/src/app/`; see [Using This Repository as a Template](../template-usage/overview.md#the-app--mystic_auth-split)), built with Vite, styled with Chakra UI v3. Feature-organized to mirror the backend's domain split, with a PBAC-aware UI layer that mirrors the backend's permission vocabulary.

---

## Module layout

| Module | Purpose |
|---|---|
| `auth/` | Login, signup, logout, logout-all, OAuth2, password reset (request/confirm), account verification (including resend), current-user session query, the auth-refresh interceptor, `useSessionEventsStream.ts` (SSE connection to `GET /auth/session-events`, invalidates the current-user/sessions queries in real time on a push event), `useCooldown` (shared resend/retry cooldown timer); each sub-feature is its own folder (Page/Form/mutation-hook/types); `password_rules/` holds password-complexity validation (`passwordRules.ts`) and its checklist UI, shared by signup/reset/account settings |
| `authorization/` | The PBAC layer: `permissions.ts` (frontend mirror of the backend `Permission` enum), `authorizationService.ts` (batch permission-check calls, policy/audit-log fetches), `useAuthorization`/`useCan` (`useAuthorized` is a same-hook alias for call sites that read more naturally as "is the caller authorized" than "can the caller"), and the gate components `Authorized`, `IfCan`, `ProtectedRoute` |
| `audit_log/` | `AuditLogPage.tsx`: just the tab shell (Authorization decisions/Security events x My activity/All users). Everything specific to just one tab lives inside its own subfolder: `authorization_log/` (`MyAuthorizationLogSection.tsx`, `AllAuthorizationLogSection.tsx`, `AuthorizationFilterBar.tsx`, `authorizationLogColumns.tsx`, `authorizationLogQueries.ts`, `authorizationLogResourceTypes.ts`) and `security_log/` (`MySecurityLogSection.tsx`, `AllSecurityLogSection.tsx`, `SecurityFilterBar.tsx`, `securityLogColumns.tsx`, `securityLogQueries.ts`, `securityLogEventTypes.ts`, `LoginTrendChart.tsx`). What's genuinely identical for both tabs stays flat at `audit_log/` instead of being duplicated into each: `auditLogListConfig.ts` (`PAGE_SIZE`/`formatTimestamp`/etc.) and `auditLogPageResult.ts` (`X-Total-Count` -> `{rows,total}` parsing, shared by both `*LogQueries.ts` files) |
| `dashboard/` | `DashboardPage.tsx`: the landing page after login, composing account-summary stats. `manage_sessions/` (`ManageSessionsCard.tsx` plus its own `useSessionsQuery`/`useRevokeSessionMutation`/`parseUserAgent`, backed by `/auth/sessions`) and `useLastLoginQuery.ts` (most recent successful login, GET `/audit/security-log/me`) both live here rather than their own top-level folders: Dashboard is their only consumer, matching how `UserStatsCard.tsx`/`PolicyStatsCard.tsx` already live inside `users/`/`policies/` rather than being pulled out |
| `policies/` | Admin CRUD UI for PBAC policies, plus `PolicyStatsCard.tsx` |
| `account_settings/` | `AccountSettingsPage.tsx` (nav label/route: "Account Settings"): self-service rename and change/set password, via two independent forms/cards, plus own effective policies. Deliberately omits email/role/member-since/session-count, which `dashboard/` already shows as read-only context. Also `useUnsavedChangesWarning` (its only consumer) |
| `users/` | Admin user management (list, mutate, assign policies), plus `UserStatsCard.tsx` |
| `api/` | Axios-based typed call functions per backend domain (`auth_api`, `users_api`, `account_settings_api`, `policies_api`, `audit_api`), plus `axiosInstance.ts` and `apiError.ts` |
| `store/` | Zustand: `authStore.ts` (session/profile/permissions), `themeStore.ts` (light/dark); client state only, no Redux |
| `core/` | App-wide settings (`APP_NAME`, `VITE_API_BASE_URL`), `queryClient.ts` (the shared TanStack Query client), and `errorMonitoring.ts` (a no-op unless `VITE_SENTRY_DSN` is set, which the default self-hosted Bugsink service sets automatically, see [Error Monitoring](../error-monitoring/overview.md)) |
| `layout/` | App shell: `AppLayout`, `Navbar`, `Sidebar`, `ThemeToggle`, `navItems.ts`. `AppLayout` takes an optional `extraNavItems: NavItem[]` prop so your own feature routes can add sidebar links without editing `navItems.ts` (upstream-owned), and an optional `extraNavbarContent: React.ReactNode` prop so you can add your own top-bar content (buttons, icons, ...) without editing `Navbar.tsx`. See [Using This Repository as a Template: shared-chrome extension points](../template-usage/overview.md#shared-chrome-extension-points) |
| `ui/` | Generic reusable UI kit, no feature ownership: `DataTable` (sortable columns, loading/error/empty states), `Pagination`, `StyledSelect`, `ConfirmDialog`, `FormAlert`, `PageContainer`, `Card`, `TableActionButton`, `LoadingState`, `ErrorBoundary`, `dateFormat.ts` (fixed-locale date/time formatting, shared by `dashboard/` and its `manage_sessions/` subfolder). Single-file components live flat at the top level. Multi-file groups get subfolders: `ui/toaster/` (`toaster.tsx` + `toasterInstance.ts`), `ui/styles/` (`buttonStyles.ts`, `inputStyles.ts`, `dialogStyles.ts`), and `ui/hooks/` (`useSortState`, `useDebouncedValue`, `usePageResetOn`). See [List pages](#list-pages-pagination-sorting-filtering) below |
| `theme/` | `system.ts`: Chakra UI v3 design tokens |
| `sdk.ts` | Public extension surface for your own feature code: the intended single import point for anything you build on top of this template, rather than reaching into the internal modules above directly. Groups roughly into: **PBAC** (`PERMISSIONS`, `useAuthorization`, `useCan`/`useAuthorized`, `Authorized`, `IfCan`, `ProtectedRoute`, `authorizationService`), **API/session** (`api`, `extractApiErrorMessage`, `useAuthStore`, `queryClient`, `settings`/`APP_NAME`, `reportError`), **app shell** (`AppLayout`, `NavItem`, `Toaster`, `toaster`), and **generic UI primitives** (`LoadingState`, `Card`, `PageContainer`, `DataTable`/`DataTableColumn`, `ConfirmDialog`, `FormAlert`, `ErrorBoundary`). See [Using This Repository as a Template: the app/ + mystic_auth split](../template-usage/overview.md#the-app--mystic_auth-split) |

This layout is feature/page-first, not a layer-first (`components/`/`hooks`/`services`) MVC structure. A file's folder tells you which page or feature it belongs to, not what kind of file it is. Where a feature maps onto exactly one backend domain (`auth/`, `authorization/`), the folder names line up with the backend's own split (`backend/mystic_auth/auth/`, `backend/mystic_auth/authorization/`). That is a side effect of "one folder per thing," not the organizing principle itself. `dashboard/`'s `manage_sessions/` and `useLastLoginQuery.ts` are named for the page that renders them, not the backend module they happen to call. `UserStatsCard.tsx` and `PolicyStatsCard.tsx` live inside `users/` and `policies/` rather than a separate `stats/` domain folder for the same reason. `api/`, `store/`, `core/`, `layout/`, `ui/`, and `theme/` are the exceptions. They are infrastructure or cross-cutting concerns with no single feature owner.

---

## State management

- **Zustand** for client state: `store/authStore.ts` (`isAuthenticated`, `name`, `email`, `role`, `permissions`, `hasPassword`) and `store/themeStore.ts` (light/dark). No Redux.
- **TanStack Query** for all server state/caching, via one shared `QueryClient` (`core/queryClient.ts`).
- `authStore.isAuthenticated` starts as `null` ("not checked yet"), so `App.tsx` blocks rendering the router behind a loading screen until `useAuthSession()` resolves it to `true`/`false`, avoiding a flash of unauthenticated content.

---

## API layer

`api/axiosInstance.ts` is a single Axios instance with `withCredentials: true`, using a base URL from `VITE_API_BASE_URL`. The JWT itself is never stored in JS-accessible state. See [Authentication Overview](../authentication/overview.md#tokens-and-cookies). Per-domain typed call functions live in `api/*.ts` (`auth_api`, `users_api`, `account_settings_api`, `policies_api`, `audit_api`). `api/apiError.ts` shapes error responses uniformly. `users_api.ts` (admin user management) and `account_settings_api.ts` (self-service `PUT /users/me`) are separate modules because they have different callers and permission requirements, mirroring the backend split into `user_management_query_routes.py`/`user_management_update_routes.py`/`user_lifecycle_routes.py` and `user_self_service_routes.py`.

`auth/session_lifecycle/setupAuthInterceptor.ts` implements silent-refresh-on-401: a single in-flight refresh call is shared across concurrently-failing requests (no thundering herd of refresh calls), and login/signup/refresh/logout/reset/verify/oauth2 endpoints are excluded from the retry-after-refresh logic to avoid infinite loops. On an unrecoverable 401, it marks `authStore` unauthenticated and clears the cached `GET /auth/me` query. It does not handle `403`; permission failures are left entirely to route/component-level guards (`ProtectedRoute`, `Authorized`, `IfCan`). It lives under `auth/session_lifecycle/`, not `api/`, since it's auth-session business logic that happens to configure the shared Axios instance, not a typed API call itself.

---

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
| `/account-settings` | authenticated | `AccountSettingsPage.tsx`; nav label "Account Settings" |
| `/login`, `/signup`, `/verify-account`, `/password-reset-request`, `/reset-password` | public | |
| `/not-authorized` | public | 403 landing, where `ProtectedRoute` sends an authenticated-but-unauthorized user |
| `*` | public | 404 |

All protected routes are wrapped in `ProtectedRoute`, which redirects
unauthenticated users to `/login` and unauthorized users to `/not-authorized`.
`AppLayout` provides the sidebar and top-bar shell, so the shell renders only
after access is confirmed.

---

## Authorization on the frontend (PBAC-aware UI)

- `authorization/permissions.ts` mirrors the backend's `Permission` enum as string constants, so route/component gates reference `PERMISSIONS.USERS_LIST_ALL` rather than a hand-typed string.
- `authorization/useAuthorization.ts` reads `authStore.permissions` and exposes `can(action)`, failing closed (`false`) when unauthenticated or still loading. This is a **client-side UX convenience only**: the backend independently enforces every action via `require_authorization` (see [PBAC Architecture](../authorization/architecture.md)); a hidden button is not a security boundary.
- `authorization/ProtectedRoute.tsx`, `Authorized.tsx`, `IfCan.tsx`: route-level and in-page conditional gates built on `useAuthorization`.
- `authorization/authorizationService.ts` layers real per-resource/conditional checks (`POST /authorization/batch-check`) on top of the cached flat permission list for cases that need it.
- `role` is explicitly treated as metadata only on the frontend too, never used in a gating decision, mirroring the backend's own design (see [Security Decisions: role is never used to decide access](../security/decisions.md#role-is-never-used-to-decide-access)).

---

## List pages: pagination, sorting, filtering

Every admin list page (`UsersPage`, `AuditLogPage`'s four log views) follows the same pattern, server-side end to end: nothing is ever paged/sorted/filtered by loading everything and slicing it in the browser. To add another one:

- **Pagination**: track `page` in local state (`useState(1)`), fetch with `limit`/`offset = (page - 1) * pageSize`, render `<Pagination page={page} totalPages={...} onPageChange={setPage} />` above and below the table. `totalPages` comes from `Math.ceil(total / pageSize)`, where `total` is read off the backend's `X-Total-Count` response header (see [API Reference: list endpoint conventions](../api/reference.md#list-endpoint-conventions)), not the page's own row count.
- **Sorting**: mark sortable `DataTableColumn`s with `sortable: true` (the column's `key` doubles as the `sort_by` value sent to the backend, so it must match one of that endpoint's own allowlisted sortable columns); wire `useSortState()` into the table's `sort`/`onSortChange` props. Clicking an unsorted column sorts ascending; clicking the same column again flips to descending; clicking a different column starts that one fresh at ascending (standard spreadsheet convention).
- **Filtering**: a `NativeSelect` per fixed-vocabulary field (role, event type, allowed/success, ...) plus a debounced `Input` (`useDebouncedValue`) for free-text fields (email search, IP substring). An empty/"All ..." option maps to `undefined`, not an empty string, so it's omitted from the request entirely rather than sent as a real (and wrong) filter value.
- **Resetting to page 1**: any search/filter/sort change can make the current page invalid. `ui/hooks/usePageResetOn.ts` takes a single `resetKey` string concatenating every filter/sort value and compares it against its previous render. It uses the same "adjust state during render" pattern that `PolicyFormDialog` and `UserPoliciesDialog` use for reset-on-open, avoiding an extra render. `UsersPage.tsx` and every `audit_log/` section component share it instead of reimplementing the same behavior.
- **Backend counterpart**: each such endpoint validates `sort_by` against an explicit allowlist (never a caller-supplied column name reaching the query directly) and computes `X-Total-Count` from the exact same filters as the row query, so the reported page count always matches what's actually being paged through. See `user_base_crud.py` and the two audit log repositories for the reference implementation.

---

## Theming

Chakra UI v3 (`@chakra-ui/react` + Emotion). `theme/system.ts` defines the design tokens; `store/themeStore.ts` + `layout/ThemeToggle.tsx` handle light/dark switching, independent of the OS-level `prefers-color-scheme`.

---

## Build & bundling

`vite.config.ts` uses Rollup's default automatic chunking, not `build.rollupOptions.output.manualChunks`. A prior version manually split every `node_modules` import into one `vendor` chunk (for better long-term browser-cache reuse: a deploy that only touches app code wouldn't have busted the cache for third-party code that hadn't changed). That was reverted after it broke production: app code like `api/axiosInstance.ts` both imports from and gets imported by the vendor chunk, and Rollup placed shared CJS-interop helpers into `axiosInstance`'s own chunk, creating a real circular chunk dependency. ESM's live-binding semantics for circular imports meant `vendor.js` called a binding from `axiosInstance.js`'s chunk before that chunk's module body had run far enough to define it, throwing `"TypeError: t is not a function"` at the very top of the vendor bundle: the whole app failed to mount, a blank page with no build-time warning. See the comment in `vite.config.ts` for the full account. Re-introducing manual chunking is possible later, but only with real production verification (not just a local build) that nothing crashes.

The build still trips Vite's "chunk larger than 500 kB" warning on the main entry chunk. The bulk of it is Chakra UI v3's `defaultConfig` (imported by `theme/system.ts`, required at the app root by `ChakraProvider`): it's one object bundling style recipes for *every* built-in Chakra component, including several this app never renders (Menu, Combobox, TreeView, TagsInput, NumberInput, ColorPicker). Rollup can tree-shake unused *modules* but not unused *properties* of an object that's genuinely referenced, so their `@zag-js/*` machine code (~150 kB+ unminified) comes along regardless. There's no supported way to hand-pick a subset of Chakra's default recipes without forking the theme system, so this is treated as a justified, inherent cost of the library choice rather than something to chase; `build.chunkSizeWarningLimit` is deliberately left untouched so the warning stays visible instead of being silenced.

Route-level code splitting is separate and already in place. See [Routing](#routing) above: every route except `LoginPage` is `React.lazy`-loaded, so route chunks only ever contain that page's own code plus the Chakra sub-components it specifically imports.

---

## Configuration requirements

`VITE_API_BASE_URL` (the backend's base URL) and `VITE_APP_NAME` (the product name shown in the UI: navbar, auth pages, document title via `index.html`'s `%VITE_APP_NAME%` substitution). Both are Vite build-time env vars, read through `core/settings.ts`, and set in the root `.env`; running the stack via Docker, that's what the frontend container actually reads. `frontend/.env.example` only matters for running the frontend locally with `npm run dev`, outside Docker. Support email shown in emails is backend-driven (`SUPPORT_EMAIL`) and only ever appears in server-rendered email templates, not in the frontend build.

---

## Edge cases / error handling

- A 401 mid-session (expired access token) triggers one silent refresh-and-retry; a second failure marks the session invalid and, per route, redirects to `/login`.
- A session revoked elsewhere (logout-all, a targeted Manage Sessions revoke, password change) is pushed to every open tab within milliseconds via `useSessionEventsStream.ts`'s SSE connection, not discovered only on the next request or poll. See [Session Management: Real-time push](../authentication/session-management.md#real-time-push).
- A 403 (authorization denial) is a normal API response the calling component/page is responsible for handling: typically a toast or an inline `FormAlert`, not a global redirect (except at the route level via `ProtectedRoute`).
- An uncaught render-time error anywhere in the tree (a bad API response shape reaching a component that doesn't expect it, a null-pointer bug, etc.) is caught by `ui/ErrorBoundary.tsx`, mounted once at the app root in `main.tsx` (outside the router, so it also catches an error thrown before routing itself renders). Shows a "Something went wrong" fallback with a full-page reload action instead of React unmounting the entire tree to a blank white screen. Always logs to the console; also reports to `core/errorMonitoring.ts` (a no-op unless `VITE_SENTRY_DSN` is set, see [Error Monitoring](../error-monitoring/overview.md)).

---

## Testing coverage

Tests live in `tests/frontend/` (outside `src/`), not co-located. Vitest + React Testing Library + jsdom + axios-mock-adapter. See [Testing Overview](../testing/overview.md) for the full breakdown and known coverage gaps.
