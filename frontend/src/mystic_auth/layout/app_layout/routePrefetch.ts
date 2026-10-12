/**
 * Maps each built-in NAV_ITEMS path to the same dynamic import() App.tsx
 * already wraps in trackedLazy(). Calling it again here doesn't create a
 * second chunk: Vite/Rollup's module cache resolves the already-split chunk,
 * so this just warms it ahead of navigation.
 *
 * Used by Sidebar's hover handler: a user hovering a nav link is likely
 * about to click it, so fetching the chunk on hover hides the network round
 * trip instead of it showing up as a RouteProgressBar flash after the click.
 *
 * Only covers the built-ins; an app's own `extraNavItems` fall back to the
 * ordinary click-triggered lazy load.
 */
const ROUTE_PREFETCH: Record<string, () => Promise<unknown>> = {
    "/dashboard": () => import("../../dashboard/DashboardPage"),
    "/users": () => import("../../users/UsersPage"),
    "/policies": () => import("../../policies/PoliciesPage"),
    "/audit-log": () => import("../../audit_log/AuditLogPage"),
    "/account-settings": () => import("../../account_settings/AccountSettingsPage"),
};

// Once a chunk import has resolved (or is in flight), don't re-trigger it on
// later hovers of the same link.
const requested = new Set<string>();

export function prefetchRoute(to: string): void {
    if (requested.has(to)) return;
    const load = ROUTE_PREFETCH[to];
    if (!load) return;
    requested.add(to);
    load().catch(() => {
        // A failed prefetch (offline, flaky network) isn't fatal: the real
        // navigation's Suspense/error handling covers it. Allow a retry.
        requested.delete(to);
    });
}
