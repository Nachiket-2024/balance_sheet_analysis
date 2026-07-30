import { PERMISSIONS } from "../authorization/permissions";

export interface NavItem {
    label: string;
    to: string;
    /** Omit for links every authenticated user should see regardless of permissions. */
    permission?: string;
    /**
     * Sort key the Sidebar merges built-in and app-supplied (`extraNavItems`)
     * items by: lower renders first. Every built-in item below has one, in
     * steps of 10, specifically so an app can slot a link between any two of
     * them (e.g. `order: 15` lands between Dashboard and Users) without
     * needing to know anyone else's exact values, just the gap either side
     * of where it wants to land.
     *
     * Omitting `order` is intentional, not an oversight: an item with none
     * always sorts after every item that has one (ties broken by array
     * order), which is what makes adding `extraNavItems` without an `order`
     * a purely additive, non-breaking change: that's the original
     * append-only behavior, still the default when you don't need to
     * interleave with the built-ins.
     */
    order?: number;
}

/**
 * Single source of truth for the sidebar's built-in link list. Items with a
 * `permission` are wrapped in IfCan by the Sidebar, so a caller who lacks
 * that permission simply never sees the link, the corresponding route is
 * still independently enforced by ProtectedRoute (and ultimately the
 * backend), this just keeps the nav from advertising pages a user can't
 * open.
 *
 * Downstream apps add their own links via AppLayout's `extraNavItems` prop
 * (same NavItem shape, re-exported from sdk.ts) rather than editing this
 * array directly, see
 * docs/mystic_auth/template-usage/overview.md#shared-chrome-extension-points.
 */
export const NAV_ITEMS: NavItem[] = [
    { label: "Dashboard", to: "/dashboard", order: 10 },
    { label: "Users", to: "/users", permission: PERMISSIONS.USERS_LIST_ALL, order: 20 },
    { label: "Policies", to: "/policies", permission: PERMISSIONS.POLICIES_READ, order: 30 },
    // No permission required: every authenticated user can view their own
    // audit trail (GET /authorization/audit-log/me, GET /audit/security-log/me)
    // The page itself additionally shows an "All Users" tab gated by
    // policies:read/security_audit:read for callers who hold those.
    { label: "Audit Log", to: "/audit-log", order: 40 },
    { label: "Profile", to: "/profile", order: 50 },
];
