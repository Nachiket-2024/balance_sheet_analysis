# Frontend Architecture
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md) or [Frontend Glossary](../glossary/frontend.md).*

## Purpose

React 19 + TypeScript SPA (`frontend/src/mystic_auth/`, with the entry point and extension surface, namely `main.tsx`, `App.tsx`, `sdk.ts`, `app_sdk.ts`, in the sibling `frontend/src/app/`; see [Using This Repository as a Template](../template-usage/ownership-split.md)), built with Vite, styled with Tailwind v4 + shadcn/ui (Radix primitives). Feature-organized to mirror the backend's domain split, with a PBAC-aware UI layer that mirrors the backend's permission vocabulary.

---

## Module layout

| Module | Purpose |
|---|---|
| `auth/` | Login, signup, logout, logout-all, OAuth2, password reset (request/confirm), account verification (including resend), current-user session query, the auth-refresh interceptor, `useSessionEventsStream.ts` (SSE connection to `GET /auth/session-events`, invalidates the current-user/sessions queries in real time on a push event), `useCooldown` (shared resend/retry cooldown timer); each sub-feature is its own folder (Page/Form/mutation-hook/types); `password_rules/` holds password-complexity validation (`passwordRules.ts`) and its checklist UI, shared by signup/reset/account settings |
| `authorization/` | The PBAC layer: `permissions.ts` (frontend mirror of the backend `Permission` enum), `authorizationService.ts` (batch permission-check calls, policy/audit-log fetches), `useAuthorization`/`useCan` (`useAuthorized` is a same-hook alias for call sites that read more naturally as "is the caller authorized" than "can the caller"), and the gate components `Authorized`, `IfCan`, `ProtectedRoute` |
| `audit_log/` | `AuditLogPage.tsx`: just the tab shell (Authorization decisions/Security events x My activity/All users). Everything specific to just one tab lives inside its own subfolder: `authorization_log/` (`MyAuthorizationLogSection.tsx`, `AllAuthorizationLogSection.tsx`, `AuthorizationFilterBar.tsx`, `authorizationLogColumns.tsx`, `authorizationLogQueries.ts`, `authorizationLogResourceTypes.ts`) and `security_log/` (`MySecurityLogSection.tsx`, `AllSecurityLogSection.tsx`, `SecurityFilterBar.tsx`, `securityLogColumns.tsx`, `securityLogQueries.ts`, `securityLogEventTypes.ts`, `LoginTrendChart.tsx`). What's genuinely identical for both tabs stays flat at `audit_log/` instead of being duplicated into each: `auditLogListConfig.ts` (`PAGE_SIZE`/`formatTimestamp`/etc.) and `auditLogPageResult.ts` (`X-Total-Count` -> `{rows,total}` parsing, shared by both `*LogQueries.ts` files) |
| `dashboard/` | `DashboardPage.tsx`: the landing page after login - data-fetching and dialog orchestration only. `DashboardIdentityCard.tsx` (plus `DashboardStatItem.tsx`, its one stat-cell subcomponent) and `DashboardIdentityCardSkeleton.tsx` own the identity-card banner's loaded/loading presentation respectively, split out of `DashboardPage.tsx` once that file passed this repo's own file-length guideline - see [Testing Overview](../testing/overview.md#file-length). `usePreviousLoginQuery.ts` (most recent successful login, GET `/audit/security-log/me`) lives here rather than its own top-level folder: Dashboard is its only consumer, matching how `UserStatsCard.tsx`/`PolicyStatsCard.tsx` already live inside `users/`/`policies/` rather than being pulled out. `OperationsShortcutsCard.tsx` owns the dashboard's operational shortcuts. |
| `active_sessions/` | `ActiveSessionsCard.tsx` (renamed from `ManageSessionsCard.tsx`, moved out of `dashboard/` into its own top-level folder since a growing set of pages other than Dashboard now render it too) plus its own `useSessionsQuery`/`useRevokeSessionMutation`/`parseUserAgent`/`activeSessionsTable.tsx`, backed by `/auth/sessions` |
| `policies/` | Policy CRUD UI for PBAC policies, plus `PolicyStatsCard.tsx` |
| `permissions/` | `PermissionsPage.tsx`: read-only, browsable view of MysticAuth's built-in permission catalog (`GET /authorization/permissions/catalog`, see `authorization/permissions_catalog.py`). It is separate from `policies/` because the built-in reference and policy composition answer different questions. Downstream applications own their custom action catalog and management UI. Search, filter, sort, and pagination run client-side against the small built-in catalog |
| `rate_limits/` | `RateLimitsPage.tsx`: operational view of [`RateLimitDashboardService.list_active_limits`](../security/hardening-abuse-prevention.md#rate-limit-dashboard-get-rate-limits) (`GET /rate-limits`), filterable by `scope` (`ip`/`account`/`email`) via `RateLimitsFilterBar.tsx`, plus `useResetRateLimitMutation` (`rateLimitsMutations.ts`) for `DELETE /rate-limits/{key:path}` |
| `account_settings/` | `AccountSettingsPage.tsx` (nav label/route: "Account Settings"): self-service rename and change/set password, via two independent forms/cards, plus own effective policies. Deliberately omits email/role/member-since/session-count, which `dashboard/` already shows as read-only context. Also `useUnsavedChangesWarning` (its only consumer). `DeleteAccountCard.tsx` and its `useDeleteMyAccountMutation` drive self-service account deletion (password re-confirm for password accounts, an emailed confirm link for OAuth-only accounts); `account_settings/confirm_delete/ConfirmDeleteAccountPage.tsx` is the public `/confirm-delete` landing page the emailed link opens. See [Account Deletion and Purge](../authentication/account-deletion/README.md) |
| `users/` | User management under PBAC policy checks (list, mutate, assign policies), plus `UserStatsCard.tsx` |
| `api/` | Axios-based typed call functions per backend domain (`auth_api`, `users_api`, `account_settings_api`, `policies_api`, `permissions_api`, `bulk_assignment_api`, `rate_limits_api`, `audit_api`), plus `axiosInstance.ts` and `apiError.ts`. The policy query modules under `policies/queries/` wrap these clients for TanStack Query mutations. |
| `store/` | Zustand: `authStore.ts` (session/profile/permissions), `themeStore.ts` (light/dark), `appearanceStore.ts` (the signed-in user's picked brand color, backed by `localStorage`, see [Appearance](../appearance/overview.md)), `languageStore.ts` (translation language mode, see [Translations Overview](../translations/overview/README.md)), `fontSizeStore.ts` (small/medium/large, persisted to `localStorage`, applied as a percentage of the browser's own root font size so it composes with the user's OS/browser text-size setting), `routeLoadingStore.ts` (in-flight lazy-route-chunk counter, drives `ui/routing/RouteProgressBar.tsx`), `networkStatusStore.ts` (`navigator.onLine` mirrored via the `online`/`offline` window events, drives `ui/network/OfflineBanner.tsx`); client state only, no Redux |
| `core/` | App-wide settings (`APP_NAME`, `VITE_API_BASE_URL`), `queryClient.ts` (the shared TanStack Query client), and `errorMonitoring.ts` (a no-op unless `VITE_SENTRY_DSN` is set, which the default self-hosted Bugsink service sets automatically, see [Error Monitoring](../error-monitoring/overview.md)) |
| `layout/` | App shell: `AppLayout`, `Navbar`, `Sidebar`, `ThemeToggle`, `LanguageToggle`, `FontSizeControl`, `navItems.ts`. `AppLayout` takes an optional `extraNavItems: NavItem[]` prop so your own feature routes can add sidebar links without editing `navItems.ts` (upstream-owned), an optional `extraNavbarContent: React.ReactNode` prop so you can add your own top-bar content (buttons, icons, ...) without editing `Navbar.tsx`, and an optional `onOpenCommandPalette: () => void` prop that renders the navbar's search-trigger button for the command palette below. See [Frontend Customization: shared-chrome extension points](../template-usage/frontend-customization.md#shared-chrome-extension-points). Also `CommandPalette.tsx` (Cmd+K/Ctrl+K quick-jump: gated nav destinations, in-page content, and, if permitted, user accounts; result-building logic in `CommandPaletteResults.ts`, row rendering in `CommandPaletteResultsList.tsx`), mounted once at the app root in `App.tsx` alongside the global keydown listener that toggles it |
| `ui/` | Generic reusable UI kit, no feature ownership. App-owned components use concrete folders that say what they contain: `buttons/` (Button and `button-variants.ts`), `inputs/` (Input, Textarea, PasswordInput and `input-variants.ts`), `cards/` (Card), `badges/` (Badge), `links/` (AuthInlineLink), `feedback/` (ConfirmDialog, FormAlert, LoadingState and result/tooltip helpers), `navigation/` (Breadcrumbs, PageContainer, Pagination and section controls), `filters/` (search, select, segmented and time-range controls), `display/` (drawers, collapsible sections, glossary help and stat tiles), `dates/` (`dateFormatters.ts`), and `styles/` (`classNames.ts`, `dialogStyles.ts`, `inputStyles.ts`). Multi-file groups remain in their dedicated folders: `DataTable/`, `table_actions/`, `toaster/`, `hooks/`, `network/`, and `routing/`. `hooks/` is the conventional React Hooks folder for `useSomething` files. The `shadcn/` folder stays flat because each file is an independently generated Radix primitive. See [List pages](#list-pages-pagination-sorting-filtering) below |
| `theme/` | `tailwind.css`: design tokens as plain CSS custom properties, seeded from `BRAND_COLOR`/`VITE_BRAND_COLOR` via `generateBrandScale.ts`. `applyBrandCssVars.ts`/`appearanceThemeOverrides.ts` write the `--brand-*`/`--bg-canvas-from`/`--bg-sidebar` variables live when a signed-in user picks their own brand color or toggles light/dark; `applyFaviconAndMetaColor.ts`/`brandIcon.ts` update the favicon and `theme-color` meta tag to match. See [Appearance](../appearance/overview.md) for the full mechanism |
| `sdk.ts` | Public extension surface for your own feature code: the intended single import point for anything you build on top of this template, rather than reaching into the internal modules above directly. Groups roughly into: **PBAC** (`PERMISSIONS`, `useAuthorization`, `useCan`/`useAuthorized`, `Authorized`, `IfCan`, `ProtectedRoute`, `authorizationService`), **API/session** (`api`, `extractApiErrorMessage`, `useAuthStore`, `queryClient`, `settings`/`APP_NAME`, `reportError`), **app shell** (`AppLayout`, `NavItem`, `Toaster`, `toaster`), and **generic UI components** (`LoadingState`, `Card`, `PageContainer`, `DataTable`/`DataTableColumn`, `ConfirmDialog`, `FormAlert`, `ErrorBoundary`). See [Using This Repository as a Template: the app/ + mystic_auth split](../template-usage/ownership-split.md) |

This layout is feature/page-first, not a layer-first (`components/`/`hooks`/`services`) MVC structure. A file's folder tells you which page or feature it belongs to, not what kind of file it is. Where a feature maps onto exactly one backend domain (`auth/`, `authorization/`), the folder names line up with the backend's own split (`backend/mystic_auth/auth/`, `backend/mystic_auth/authorization/`). That is a side effect of "one folder per thing," not the organizing principle itself. `usePreviousLoginQuery.ts` lives inside `dashboard/` because Dashboard is its only consumer. `UserStatsCard.tsx` and `PolicyStatsCard.tsx` live inside `users/` and `policies/` rather than a separate `stats/` domain folder for the same reason. `api/`, `store/`, `core/`, `layout/`, `ui/`, and `theme/` are the exceptions. They are infrastructure or cross-cutting concerns with no single feature owner.

---

## State management

- **Zustand** for client state: `store/authStore.ts` (`isAuthenticated`, `name`, `email`, `role`, `permissions`, `hasPassword`) and `store/themeStore.ts` (light/dark). No Redux.
- **TanStack Query** for all server state/caching, via one shared `QueryClient` (`core/queryClient.ts`).
- `authStore.isAuthenticated` starts as `null` ("not checked yet"), so `App.tsx` blocks rendering the router behind a loading screen until `useAuthSession()` resolves it to `true`/`false`, avoiding a flash of unauthenticated content.

---

## API layer

`api/axiosInstance.ts` is a single Axios instance with `withCredentials: true`, using a base URL from `VITE_API_BASE_URL`. The JWT itself is never stored in JS-accessible state. See [Authentication Overview](../authentication/overview.md#tokens-and-cookies). Per-domain typed call functions live in `api/*.ts` (`auth_api`, `users_api`, `account_settings_api`, `policies_api`, `audit_api`). `api/apiError.ts` shapes error responses uniformly. `users_api.ts` (policy-protected user management) and `account_settings_api.ts` (self-service `PUT /users/me`) are separate modules because they have different callers and permission requirements, mirroring the backend split into `user_management_query_routes.py`/`user_management_update_routes.py`/`user_lifecycle_routes.py` and `user_self_service_routes.py`.

`auth/session_lifecycle/setupAuthInterceptor.ts` implements silent-refresh-on-401: a single in-flight refresh call is shared across concurrently-failing requests (no thundering herd of refresh calls), and login/signup/refresh/logout/reset/verify/oauth2 endpoints are excluded from the retry-after-refresh logic to avoid infinite loops. On an unrecoverable 401, it marks `authStore` unauthenticated and clears the cached `GET /auth/me` query. It does not handle `403`; permission failures are left entirely to route/component-level guards (`ProtectedRoute`, `Authorized`, `IfCan`). It lives under `auth/session_lifecycle/`, not `api/`, since it's auth-session business logic that happens to configure the shared Axios instance, not a typed API call itself.

---

## Routing

`react-router` v8 (see [below](#why-react-router-not-react-router-dom) for why not `react-router-dom`), `BrowserRouter`, defined in `App.tsx`. Only `LoginPage` is eager-loaded (the most common unauthenticated entry point); every other route is `React.lazy`-split.

---

### Why `react-router`, not `react-router-dom`

Upstream stopped publishing `react-router-dom` past `7.18.1` and folded its exports into `react-router` for v8: everything except the RSC-only `RouterProvider`/`HydratedRouter` (under `react-router/dom`, unused here) now comes from the single `react-router` package. Not optional: `react-router-dom@7.18.1` carried an unpatched high-severity advisory ([GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)) with no further release ever published under that package name. The fix only exists as `react-router@8.3.0`.

| Route | Access | Notes |
|---|---|---|
| `/`, `/dashboard` | authenticated | `DashboardPage` |
| `/users` | `USERS_LIST_ALL` | PBAC-protected user management |
| `/policies` | `POLICIES_READ` | PBAC policy management |
| `/permissions` | `PERMISSIONS_READ` | Permission catalog browser |
| `/rate-limits` | `RATE_LIMITS_READ` | Rate limit dashboard |
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

### Route-loading UX

Every lazy-split route in `App.tsx` uses `ui/routing/trackedLazy.ts`'s `trackedLazy()` instead of plain `React.lazy()`. It wraps the same dynamic `import()` but calls `startRouteLoad()`/`finishRouteLoad()` (`store/routeLoadingStore.ts`) around it, incrementing/decrementing a `pendingCount` rather than tracking a single boolean, so two overlapping navigations (e.g. a user clicking a second link before the first chunk finishes) don't clear the loading state early. Two things react to that count:

- `ui/routing/RouteProgressBar.tsx`: a thin fixed-top indeterminate progress bar, mounted once at the app root, visible whenever `pendingCount > 0`.
- `ui/routing/RouteSkeleton.tsx`: the `<Suspense>` fallback for lazy routes. In practice this rarely renders, since React Router already wraps navigations in `startTransition`, which defers showing a fallback until the new route has had a chance to load; it exists for the rare case a route suspends before that deferral applies.

`ui/routing/RouteFadeIn.tsx` fades each route's content in on every client-side navigation (mounted alongside the two above in `App.tsx`), so a route transition never pops in abruptly even on a fast, cached load. It deliberately skips that fade for the very first render after the static boot shell (`frontend/index.html`'s pre-React "Loading your session" screen): fading real content in on top of the boot shell's own removal added a second, brief animated state between "boot shell" and "real page" that some visitors could see as two loading screens rather than one clean cut. The first paint after the boot shell is always instant, at full opacity; only a route change *within* the already-mounted app fades.

---

## Authorization on the frontend (PBAC-aware UI)

- `authorization/permissions.ts` mirrors the backend's `Permission` enum as string constants, so route/component gates reference `PERMISSIONS.USERS_LIST_ALL` rather than a hand-typed string.
- `authorization/useAuthorization.ts` reads `authStore.permissions` and exposes `can(action)`, failing closed (`false`) when unauthenticated or still loading. This is a **client-side UX convenience only**: the backend independently enforces every action via `require_authorization` (see [PBAC Architecture](../authorization/architecture/README.md)); a hidden button is not a security boundary.
- `authorization/ProtectedRoute.tsx`, `Authorized.tsx`, `IfCan.tsx`: route-level and in-page conditional gates built on `useAuthorization`.
- `authorization/authorizationService.ts` layers real per-resource/conditional checks (`POST /authorization/batch-check`) on top of the cached flat permission list for cases that need it.
- `role` is explicitly treated as metadata only on the frontend too, never used in a gating decision, mirroring the backend's own design (see [Security Decisions: role is never used to decide access](../security/decisions-auth.md#role-is-never-used-to-decide-access)).

---

## List pages: pagination, sorting, filtering

Every policy-protected list page (`UsersPage`, `AuditLogPage`'s four log views) follows the same pattern, server-side end to end: nothing is ever paged/sorted/filtered by loading everything and slicing it in the browser. To add another one:

- **Pagination**: track `page` in local state (`useState(1)`), fetch with `limit`/`offset = (page - 1) * pageSize`, render `<Pagination page={page} totalPages={...} onPageChange={setPage} />` above and below the table. `totalPages` comes from `Math.ceil(total / pageSize)`, where `total` is read off the backend's `X-Total-Count` response header (see [API Reference: list endpoint conventions](../api/reference.md#list-endpoint-conventions)), not the page's own row count.
- **Sorting**: mark sortable `DataTableColumn`s with `sortable: true` (the column's `key` doubles as the `sort_by` value sent to the backend, so it must match one of that endpoint's own allowlisted sortable columns); wire `useSortState()` into the table's `sort`/`onSortChange` props. Clicking an unsorted column sorts ascending; clicking the same column again flips to descending; clicking a different column starts that one fresh at ascending (standard spreadsheet convention).
- **Filtering**: a `NativeSelect` per fixed-vocabulary field (role, event type, allowed/success, ...) plus a debounced `Input` (`useDebouncedValue`) for free-text fields (email search, IP substring). An empty/"All ..." option maps to `undefined`, not an empty string, so it's omitted from the request entirely rather than sent as a real (and wrong) filter value.
- **Resetting to page 1**: any search/filter/sort change can make the current page invalid. `ui/hooks/usePageResetOn.ts` takes a single `resetKey` string concatenating every filter/sort value and compares it against its previous render. It uses the same "adjust state during render" pattern that `PolicyFormDialog` and `UserAccessDialog` use for reset-on-open, avoiding an extra render. `UsersPage.tsx` and every `audit_log/` section component share it instead of reimplementing the same behavior.
- **Backend counterpart**: each such endpoint validates `sort_by` against an explicit allowlist (never a caller-supplied column name reaching the query directly) and computes `X-Total-Count` from the exact same filters as the row query, so the reported page count always matches what's actually being paged through. See `user_base_crud.py` and the two audit log repositories for the reference implementation.

---

## Scrolling and `scrollbar-gutter`

Two different, deliberately different, rules govern when this app reserves space for a scrollbar versus lets the browser add one only when content actually overflows. Both are deliberate UI tradeoffs, not oversights - know which one applies before changing either.

- **Page level: always reserved.** `theme/tailwind.css`'s `body` rule sets `overflow-y: scroll; scrollbar-gutter: stable;`, and `AppLayout.tsx`'s `<main>` repeats `[scrollbar-gutter:stable]`. This means the vertical scrollbar's ~14-17px gutter is present on every page, whether that page's content is tall enough to scroll or not. The reason: without it, navigating from a short page (e.g. Dashboard) to a tall one (e.g. Users with many rows) makes the scrollbar pop in and the *entire page's content* shift sideways by its width the instant it appears. Reserving the gutter permanently trades a constant, barely-noticeable strip for eliminating that shift - the same choice common production SaaS UIs make on their outer scroll containers. Do not remove this to "fix" the always-present gutter; it is solving a worse problem than it costs.
- **Component level: reserved only when it can actually scroll.** `ui/DataTable/DataTable.tsx`'s scroll container and `ui/filters/StyledSelect.tsx`'s `.dropdown-scroll-area` (see that class's own comment in `tailwind.css`) both deliberately leave `scrollbar-gutter` at the browser default (`auto`) instead of `stable`. A 2026-09-24 audit found `DataTable.tsx` had briefly picked up `[scrollbar-gutter:stable]` in this trailing spot, which left a visible empty notch in the table's rounded corner whenever it had too few rows to need a scrollbar - since a table's or dropdown's own row count varies constantly (a filter, a search, or a user-management action) and there's no shared "user is navigating between different content" moment to protect against, unlike the page-level case, there's no reflow this gutter would be preventing, only wasted space it would be creating. If you add a new scrollable container inside a page (not the page's own outer scroll), default to `auto` and only reach for `stable` if you can point to the specific layout-shift it prevents.

---

## Theming

Tailwind v4 + shadcn/ui (Radix primitives). `theme/tailwind.css` defines the design tokens as plain CSS custom properties (a `:root` block for light values, a `.dark`-scoped block overriding what changes in dark mode, and an `@theme inline` block mapping them onto Tailwind utility classes); `store/themeStore.ts` + `layout/controls/ThemeToggle.tsx` handle light/dark switching by toggling that `.dark` class on `<html>`, independent of the OS-level `prefers-color-scheme`. `theme/applyBrandCssVars.ts` overrides the `--brand-*` steps (plus the two light/dark-dependent pairs, `--bg-canvas-from`/`--bg-sidebar`) at startup and on every brand-color change - see [Appearance](../appearance/overview.md) for how a pick flows through `generateBrandScale.ts` into those variables.

Text size is a separate, independent control: `store/fontSizeStore.ts` + `layout/controls/FontSizeControl.tsx` (a navbar dropdown, small/medium/large) scale `document.documentElement.style.fontSize` as a percentage (87.5% / 100% / 112.5%), so it multiplies with whatever base size the user's own browser/OS already has set for accessibility, rather than overriding it outright. The choice persists to `localStorage` and is applied at module load, before the app renders, to avoid a flash of default-size text.

---

## Build & bundling

`vite.config.ts` uses Rollup's default automatic chunking, not `build.rollupOptions.output.manualChunks`. A prior version manually split every `node_modules` import into one `vendor` chunk (for better long-term browser-cache reuse: a deploy that only touches app code wouldn't have busted the cache for third-party code that hadn't changed). That was reverted after it broke the production-shaped local/self-hosted build: app code like `api/axiosInstance.ts` both imports from and gets imported by the vendor chunk, and Rollup placed shared CJS-interop helpers into `axiosInstance`'s own chunk, creating a real circular chunk dependency. ESM's live-binding semantics for circular imports meant `vendor.js` called a binding from `axiosInstance.js`'s chunk before that chunk's module body had run far enough to define it, throwing `"TypeError: t is not a function"` at the very top of the vendor bundle: the whole app failed to mount, a blank page with no build-time warning. See the comment in `vite.config.ts` for the full account. Re-introducing manual chunking is possible later, but only with verification in the local-prod/self-hosted mode (not just a local build) that nothing crashes.

The main entry chunk doesn't trip Vite's "chunk larger than 500 kB" warning: each shadcn component under `ui/shadcn/` only pulls in the specific Radix primitive it wraps, rather than one shared object bundling style recipes and machine code for every possible component regardless of whether the app renders it, so the bundle reflects what the app actually renders.

Route-level code splitting is separate and already in place. See [Routing](#routing) above: every route except `LoginPage` is `React.lazy`-loaded, so route chunks only ever contain that page's own code plus the components it specifically imports.

---

## Configuration requirements

`VITE_API_BASE_URL` (the backend's base URL), `VITE_APP_NAME` (the product name shown in the UI: navbar, auth pages, document title via `index.html`'s `%VITE_APP_NAME%` substitution), `VITE_BRAND_COLOR` (the default brand color, see [Appearance: Default brand color](../appearance/overview.md#default-brand-color)), and `VITE_SUPPORT_EMAIL` (contact address, undefined by default). All are Vite build-time env vars, read through `core/settings.ts`, and set in `env/mystic_auth/.env.dev`; running the stack via Docker, that's what the frontend container actually reads. `frontend/.env.example` only matters for running the frontend locally with `npm run dev`, outside Docker. `SUPPORT_EMAIL` is shared with the backend (also used as the `Reply-To` on outgoing email, see [Background Email Delivery](../background-workers/procrastinate.md)) and, on the frontend, appears on the Terms of Service / Privacy Policy pages and, once set, as a "Help & Support" mailto link pinned to the bottom of the sidebar (`layout/app_layout/Sidebar.tsx`) - the one spot every authenticated screen shares regardless of permissions, so it stays out of a fresh fork until `SUPPORT_EMAIL` is actually configured.

---

## Edge cases / error handling

- A 401 mid-session (expired access token) triggers one silent refresh-and-retry; a second failure marks the session invalid and, per route, redirects to `/login`.
- A session revoked elsewhere (logout-all, a targeted Manage Sessions revoke, password change) is pushed to every open tab within milliseconds via `useSessionEventsStream.ts`'s SSE connection, not discovered only on the next request or poll. See [Session Management: Real-time push](../authentication/session-management/real-time-push.md#real-time-push).
- A 403 (authorization denial) is a normal API response the calling component/page is responsible for handling: typically a toast or an inline `FormAlert`, not a global redirect (except at the route level via `ProtectedRoute`).
- An uncaught render-time error anywhere in the tree (a bad API response shape reaching a component that doesn't expect it, a null-pointer bug, etc.) is caught by `ui/routing/ErrorBoundary.tsx`, mounted once at the app root in `main.tsx` (outside the router, so it also catches an error thrown before routing itself renders). Shows a "Something went wrong" fallback with a full-page reload action instead of React unmounting the entire tree to a blank white screen. Always logs to the console; also reports to `core/errorMonitoring.ts` (a no-op unless `VITE_SENTRY_DSN` is set, see [Error Monitoring](../error-monitoring/overview.md)).

---

## Testing coverage

Tests live in `tests/frontend/` (outside `src/`), not co-located. Vitest + React Testing Library + jsdom + axios-mock-adapter. See [Testing Overview](../testing/overview.md) for the full breakdown and known coverage gaps.

---
