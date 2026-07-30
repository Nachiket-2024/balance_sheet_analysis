# Architecture: SDK and Extension Points

See [Overview](overview.md) for the directory tree these rules produce.

## Why `sdk.py`/`app_sdk.py` split the way they do

Per [`template-usage/overview.md`](../../mystic_auth/template-usage/overview.md): `sdk.py` re-exports
template pieces, kept exactly as shipped so upstream updates apply cleanly.
Anything this app needs from `mystic_auth/` that isn't already in `sdk.py`
(here: `policy_repository`, for `access/scope.py`'s list-filtering logic;
`Base`, so this app's models share one declarative base/migration history
with mystic_auth's; and `rate_limiter_service`, reused to rate-limit the LLM
chat and balance-sheet import endpoints) is re-exported from **`app_sdk.py`**
instead, not added to `sdk.py`, so `sdk.py` never diverges from upstream
at all, and every addition this app needed lives in the one file that's
unambiguously ours. `app_sdk.py` also re-exports `password_service` and
`user_crud`, needed only by `app/seed/seed_demo_data.py` to create demo
users through mystic_auth's own signup path rather than inserting rows by
hand.

## Extension-surface rule: every `app/`/`frontend/src/app/` file imports through `sdk`/`app_sdk`

Per `template-usage/overview.md`'s explicit rule ("Import from HERE, not internal
paths... directly"), nothing under `backend/app/` or `frontend/src/app/`
reaches into `mystic_auth/` internals directly; it always goes through
`sdk.py`/`app_sdk.py` (backend) or `sdk.ts`/`app_sdk.ts` (frontend).
On the backend, `sdk.py` doesn't cover everything this app needs, so
`app_sdk.py` re-exports the rest (`policy_repository`, `Base`,
`rate_limiter_service`, `password_service`, `user_crud`; see above for why
those specifically). On the frontend, `sdk.ts` covers most of what this app
uses, including the generic UI primitives (`Card`, `PageContainer`,
`DataTable`, `FormAlert`, `ConfirmDialog`, `toaster`, `LoadingState`, ...),
but not `DashboardPage` itself: that one gap is what `app_sdk.ts` re-exports
(see below).

## Nav gap: `extraNavItems`, not a dashboard wrapper

`frontend/src/mystic_auth/layout/Sidebar.tsx` reads its link list from
`mystic_auth/layout/navItems.ts`, a template internal, not an extension
point. Adding "Companies" there would mean editing `mystic_auth/`, which
breaks clean upstream merges. Instead, `App.tsx` (this app's own file) passes
`AppLayout` an `extraNavItems` prop (`{ label: "Companies", to: "/companies",
order: 15, ... }`), the actual extension point `template-usage/overview.md`
documents for exactly this. `order: 15` places it between the built-in
Dashboard (`10`) and Users (`20`) entries.

An earlier version of this app routed `/dashboard` through an
`AppDashboardPage` wrapper instead, whose only job was rendering mystic_auth's
own `DashboardPage` plus a "View your companies" button, a workaround from
before `extraNavItems` was adopted for the sidebar link above. With Companies
already permanently in the sidebar, that button was a redundant second entry
point, so the wrapper was removed: `/dashboard` now renders mystic_auth's own
`DashboardPage` directly (re-exported from `app_sdk.ts`, since `sdk.ts` itself
is never-edit and doesn't cover it). Every route is still independently
protected by the reused (unedited) `ProtectedRoute`/PBAC check regardless of
how a user navigates to it.
