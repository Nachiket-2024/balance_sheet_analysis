import { Gauge, KeyRound, LayoutDashboard, ScrollText, Settings, ShieldCheck, Users, type LucideIcon } from "lucide-react";

import { PERMISSIONS } from "../../authorization/permissions";

export interface NavItem {
    /**
     * A plain display string (what app-supplied `extraNavItems` pass) or a
     * "namespace:key" translation key (what the built-ins pass, resolved via
     * t() in Sidebar). Sidebar tells the two apart with i18next's `exists()`.
     */
    label: string;
    to: string;
    /**
     * Omit for links every authenticated user should see. An array means
     * "any of" (see useAuthorization's `can`) for a page reachable via more
     * than one independent action (see the Policies entry below).
     */
    permission?: string | string[];
    /**
     * Sort key Sidebar merges built-in and app-supplied items by: lower
     * renders first. Built-ins step by 10, so an app can slot a link between
     * any two (e.g. `order: 15` lands between Dashboard and Users) without
     * knowing the others' exact values.
     *
     * Omitting `order` is intentional: such an item always sorts after every
     * item that has one, which keeps adding `extraNavItems` without an
     * `order` a purely additive, append-only change.
     */
    order?: number;
    /** Muted-gray at rest, brand-colored when the route is active (see
     * Sidebar's SidebarNavLink). Optional. Also reused by PageContainer's
     * `icon` prop, so the sidebar entry and page title share one glyph. */
    icon?: LucideIcon;
}

/**
 * Single source of truth for the sidebar's built-in link list. Items with a
 * `permission` are wrapped in IfCan by the Sidebar; the route itself is still
 * independently enforced by ProtectedRoute (and the backend) - this just
 * keeps the nav from advertising pages a user can't open.
 *
 * Downstream apps add their own links via AppLayout's `extraNavItems` prop
 * rather than editing this array directly. See
 * docs/mystic_auth/template-usage/frontend-customization.md#shared-chrome-extension-points.
 */
export const NAV_ITEMS: NavItem[] = [
    { label: "layout:nav.dashboard", to: "/dashboard", order: 10, icon: LayoutDashboard },
    { label: "layout:nav.users", to: "/users", permission: PERMISSIONS.USERS_LIST_ALL, order: 20, icon: Users },
    // policies:read OR policies:create: creating a policy needs no
    // visibility into existing ones, unlike update/delete/assign/revoke,
    // which all require finding the target via the read-gated list first.
    // See PoliciesPage's docstring for the create-but-not-read render case.
    { label: "layout:nav.policies", to: "/policies", permission: [PERMISSIONS.POLICIES_READ, PERMISSIONS.POLICIES_CREATE], order: 30, icon: ShieldCheck },
    { label: "layout:nav.permissions", to: "/permissions", permission: PERMISSIONS.PERMISSIONS_READ, order: 32, icon: KeyRound },
    { label: "layout:nav.rateLimits", to: "/rate-limits", permission: PERMISSIONS.RATE_LIMITS_READ, order: 35, icon: Gauge },
    // No permission required: every authenticated user can view their own
    // audit trail. The page itself additionally shows an "All Users" tab
    // gated by policies:read/security_audit:read.
    { label: "layout:nav.auditLog", to: "/audit-log", order: 40, icon: ScrollText },
    { label: "layout:nav.accountSettings", to: "/account-settings", order: 50, icon: Settings },
];
