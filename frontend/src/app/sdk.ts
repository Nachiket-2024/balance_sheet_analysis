/**
 * Public extension surface for feature code built on top of this template
 * (see docs/mystic_auth/template-usage/overview.md).
 *
 * Import from HERE, not internal paths like "../authorization/useAuthorization"
 * directly. One file to discover what's available, and one file to reconcile
 * when pulling in upstream template updates instead of every call site.
 *
 * Everything below is a straight re-export; see the original module for the
 * "why" behind any given piece.
 *
 * DO NOT hand-edit this file. Treat it as a drop-in you receive from
 * upstream, not a place to add your own re-exports: this is the one file a
 * `scripts/sync-upstream.sh` sync is expected to touch, and local edits
 * here are exactly what turns that sync into a manual conflict instead of
 * applying cleanly. If you need your own re-exports for your own domain
 * code, add them to app_sdk.ts instead, since it's the counterpart file kept
 * empty by upstream for exactly this purpose, so it never conflicts on a
 * sync.
 */

// PBAC: see docs/mystic_auth/authorization/architecture.md
export { PERMISSIONS } from "../mystic_auth/authorization/permissions";
export type { PermissionValue } from "../mystic_auth/authorization/permissions";
export { useAuthorization } from "../mystic_auth/authorization/useAuthorization";
export { useCan, useAuthorized } from "../mystic_auth/authorization/useCan";
export { Authorized } from "../mystic_auth/authorization/Authorized";
export { IfCan } from "../mystic_auth/authorization/IfCan";
export { default as ProtectedRoute } from "../mystic_auth/authorization/ProtectedRoute";
export * as authorizationService from "../mystic_auth/authorization/authorizationService";

// App shell: the chrome every protected page renders inside. AppLayout
// takes an optional `extraNavItems` prop (see layout/navItems.ts's NavItem)
// so your own feature routes can add sidebar links without editing
// mystic_auth/layout/navItems.ts directly, see
// docs/mystic_auth/template-usage/overview.md#shared-chrome-extension-points.
export { default as AppLayout } from "../mystic_auth/layout/AppLayout";
export type { NavItem } from "../mystic_auth/layout/navItems";

// Mount once at your app root (see App.tsx) so any component/thunk can call
// toaster.create({...})
export { Toaster } from "../mystic_auth/ui/toaster/toaster";
export { toaster } from "../mystic_auth/ui/toaster/toasterInstance";

// Generic UI primitives: no identity/PBAC coupling of their own, reused
// as-is by your own feature pages the same way this template's own pages do.
export { default as LoadingState } from "../mystic_auth/ui/LoadingState";
export { default as Card } from "../mystic_auth/ui/Card";
export { default as PageContainer } from "../mystic_auth/ui/PageContainer";
export { default as DataTable } from "../mystic_auth/ui/DataTable";
export type { DataTableColumn } from "../mystic_auth/ui/DataTable";
export { default as ConfirmDialog } from "../mystic_auth/ui/ConfirmDialog";
export { default as FormAlert } from "../mystic_auth/ui/FormAlert";
export { default as ErrorBoundary } from "../mystic_auth/ui/ErrorBoundary";

// API layer: see docs/mystic_auth/architecture/frontend.md#api-layer
export { default as api } from "../mystic_auth/api/axiosInstance";
export { extractApiErrorMessage } from "../mystic_auth/api/apiError";

// Session/client state
export { useAuthStore } from "../mystic_auth/store/authStore";
export { queryClient } from "../mystic_auth/core/queryClient";

// Settings: add your own VITE_* fields to frontend/.env.example and
// core/settings.ts, read them from here rather than import.meta.env
// directly at every call site
export { default as settings, APP_NAME } from "../mystic_auth/core/settings";

// Error monitoring: reports a caught-but-still-noteworthy error the same
// way an uncaught render error gets reported automatically (see
// ui/ErrorBoundary.tsx). A safe no-op when VITE_SENTRY_DSN is unset, see
// docs/mystic_auth/error-monitoring/overview.md
export { reportError } from "../mystic_auth/core/errorMonitoring";
