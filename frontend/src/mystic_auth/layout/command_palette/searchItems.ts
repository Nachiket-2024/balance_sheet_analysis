import { IdCard, KeyRound, Laptop, Palette, Scale, ScrollText, ShieldCheck, Trash2, type LucideIcon } from "lucide-react";

import { PERMISSIONS } from "../../authorization/permissions";
import type { Namespace } from "../../translations/translations";

/**
 * A single result CommandPalette's content search can surface: a specific
 * feature/section *within* a page (e.g. "Change Password" inside Account
 * Settings), as opposed to NavItem (navItems.ts), which is a whole page.
 * Renders in its own "Features" group, but shares permission-gating and the
 * "namespace:key" translation convention with NavItem.
 */
export interface SearchItem {
    /** Plain display string or i18next "namespace:key", resolved the same
     * way as NavItem.label. This item's primary display text. */
    label: string;
    /** Secondary text shown under `label`, e.g. distinguishing two items
     * that share a `label`. Falls back to `group` when omitted. */
    detail?: string;
    /** The page/section this item belongs to, shown as `detail`'s fallback
     * and folded into the search text so the page's own name also matches. */
    group: string;
    /** Extra translation keys/plain strings folded into the search text
     * without being displayed. Prefer `scope` below when an i18next
     * namespace exists to sweep instead, since it stays in sync on its own. */
    matchKeys?: string[];
    /** Sweeps every string under these dot-paths within one i18next
     * namespace into this item's (invisible) search text - e.g.
     * `{ namespace: "account_settings", paths: ["tabs.password",
     * "changePassword"] }` matches any word actually rendered on the Change
     * Password tab, and stays correct as that copy changes. Combine with
     * `matchKeys` for one-off terms in a different namespace. */
    scope?: { namespace: Namespace; paths: string[] };
    /** Destination, e.g. "/account-settings?tab=password" (a query param a
     * page reads on mount to select a tab) or a `#hash` AppLayout's
     * useScrollToHash scrolls to, for a page section rather than a whole
     * tab - none of the built-ins below need the latter right now, but an
     * app's own extraSearchItems can still use it. */
    to: string;
    /** Omit for items every authenticated user should see. An array means
     * "any of" - see useAuthorization's `can` and NavItem.permission. */
    permission?: string | string[];
    icon?: LucideIcon;
}

/**
 * Single source of truth for the palette's built-in content-search results.
 * Downstream apps add their own via CommandPalette's `extraSearchItems`
 * prop rather than editing this array directly. See
 * docs/mystic_auth/template-usage/frontend-customization.md#shared-chrome-extension-points.
 */
export const SEARCH_ITEMS: SearchItem[] = [
    {
        label: "account_settings:tabs.password",
        group: "account_settings:pageTitle",
        scope: { namespace: "account_settings", paths: ["tabs.password", "changePassword"] },
        to: "/account-settings?tab=password",
        icon: KeyRound,
    },
    {
        label: "account_settings:tabs.profile",
        group: "account_settings:pageTitle",
        scope: { namespace: "account_settings", paths: ["tabs.profile", "profileName"] },
        to: "/account-settings?tab=profile",
        icon: IdCard,
    },
    {
        label: "account_settings:tabs.status",
        group: "account_settings:pageTitle",
        scope: { namespace: "account_settings", paths: ["tabs.status", "accountStatus"] },
        to: "/account-settings?tab=status",
        icon: ShieldCheck,
    },
    {
        label: "account_settings:tabs.appearance",
        group: "account_settings:pageTitle",
        scope: { namespace: "account_settings", paths: ["tabs.appearance", "appearance"] },
        to: "/account-settings?tab=appearance",
        icon: Palette,
    },
    {
        label: "account_settings:tabs.legal",
        group: "account_settings:pageTitle",
        to: "/account-settings?tab=legal",
        icon: Scale,
    },
    {
        label: "account_settings:tabs.danger",
        group: "account_settings:pageTitle",
        scope: { namespace: "account_settings", paths: ["tabs.danger", "deleteAccount"] },
        to: "/account-settings?tab=danger",
        icon: Trash2,
    },
    {
        label: "dashboard:activeSessionsCard.heading",
        group: "layout:nav.dashboard",
        scope: { namespace: "dashboard", paths: ["activeSessionsCard", "parseUserAgent"] },
        to: "/dashboard",
        icon: Laptop,
    },
    {
        label: "audit_log:tabs.authorizationDecisions",
        detail: "audit_log:tabs.myActivity",
        group: "audit_log:page.title",
        scope: { namespace: "audit_log", paths: ["tabs.authorizationDecisions", "tabs.myActivity", "authorization"] },
        to: "/audit-log?category=authorization&scope=mine",
        icon: ScrollText,
    },
    {
        label: "audit_log:tabs.authorizationDecisions",
        detail: "audit_log:tabs.allUsers",
        group: "audit_log:page.title",
        scope: { namespace: "audit_log", paths: ["tabs.authorizationDecisions", "tabs.allUsers", "authorization"] },
        to: "/audit-log?category=authorization&scope=all",
        permission: PERMISSIONS.POLICIES_READ,
        icon: ScrollText,
    },
    {
        label: "audit_log:tabs.securityEvents",
        detail: "audit_log:tabs.myActivity",
        group: "audit_log:page.title",
        scope: { namespace: "audit_log", paths: ["tabs.securityEvents", "tabs.myActivity", "security"] },
        to: "/audit-log?category=security&scope=mine",
        icon: ScrollText,
    },
    {
        label: "audit_log:tabs.securityEvents",
        detail: "audit_log:tabs.allUsers",
        group: "audit_log:page.title",
        scope: { namespace: "audit_log", paths: ["tabs.securityEvents", "tabs.allUsers", "security"] },
        to: "/audit-log?category=security&scope=all",
        permission: PERMISSIONS.SECURITY_AUDIT_READ,
        icon: ScrollText,
    },
];

/**
 * Which i18next namespace(s) hold a built-in page's own rendered copy,
 * swept into that page's "Pages" result the same way SearchItem.scope
 * sweeps a "Features" result - so e.g. "purge" or "reactivate" (real
 * strings on the Users page) surfaces "Users" too, not just its nav label.
 * Keyed by route, not label. Pages without an entry here only match by nav
 * label.
 */
export const PAGE_CONTENT_NAMESPACES: Partial<Record<string, Namespace[]>> = {
    "/dashboard": ["dashboard"],
    "/users": ["users"],
    "/policies": ["policies"],
    "/permissions": ["permissions"],
    "/rate-limits": ["rate_limits"],
    "/audit-log": ["audit_log"],
    "/account-settings": ["account_settings"],
};
