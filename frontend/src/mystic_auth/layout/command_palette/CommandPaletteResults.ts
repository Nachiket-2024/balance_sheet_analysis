import React, { useMemo } from "react";
import { KeyRound, LayoutDashboard, ScrollText, Settings, ShieldCheck, Users } from "lucide-react";

import { useAuthorization } from "../../authorization/useAuthorization";
import { PERMISSIONS } from "../../authorization/permissions";
import { NAV_ITEMS, type NavItem } from "../app_layout/navItems";
import { SEARCH_ITEMS, PAGE_CONTENT_NAMESPACES, type SearchItem } from "./searchItems";
import { useLanguageStore } from "../../store/languageStore";
import translations from "../../translations/translations";
import { namespaceMatches, namespaceSearchText, scopedMatches, scopedSearchText } from "../../translations/searchText";
import { useUsersQuery } from "../../users/queries/userQueries";
import { usePermissionCatalogQuery } from "../../policies/queries/permissionQueries";
import { usePoliciesListQuery } from "../../policies/queries/policyQueries";

const USER_RESULTS_LIMIT = 5;
const POLICY_RESULTS_LIMIT = 5;
const TEXT_MATCH_RESULTS_LIMIT = 20;

// Same routes as Sidebar's NAV_ITEMS, keyed by `to`. A missing entry just
// renders no icon, not a crash.
const ROUTE_ICONS: Record<string, React.ElementType> = {
    "/dashboard": LayoutDashboard,
    "/users": Users,
    "/policies": ShieldCheck,
    "/audit-log": ScrollText,
    "/account-settings": Settings,
};

export type ResultKind = "page" | "content" | "match" | "user" | "policy";

export interface Result {
    kind: ResultKind;
    to: string;
    label: string;
    sublabel?: string;
    icon?: React.ElementType;
}

export const GROUP_LABEL_KEY: Record<ResultKind, string> = {
    page: "commandPalette.pagesGroup",
    content: "commandPalette.featuresGroup",
    match: "commandPalette.matchesGroup",
    user: "commandPalette.usersGroup",
    policy: "commandPalette.policiesGroup",
};

/**
 * Builds CommandPalette's result groups (pages, in-page features,
 * Ctrl+F-style text matches, live policy search, and live user search) for a given query. See
 * CommandPalette.tsx's docstring for what each group searches.
 */
export function useCommandPaletteResults(
    trimmedQuery: string,
    extraNavItems: NavItem[] | undefined,
    extraSearchItems: SearchItem[] | undefined
) {
    const { can } = useAuthorization();
    const q = trimmedQuery.toLowerCase();

    // Nav/content item labels are chrome, not page content, so they resolve
    // via chromeLanguage - same reasoning as Sidebar's resolveLabel. Plain
    // (non-translation-key) strings pass through unchanged.
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    const tChrome = translations.getFixedT(chromeLanguage, "layout");
    const resolveLabel = (label: string): string =>
        translations.exists(label, { lng: chromeLanguage }) ? tChrome(label) : label;

    // {result, haystack} built once per language/permission change, not per
    // keystroke, then scanned with `.includes(q)` below. haystack sweeps
    // each page's full i18next namespace (PAGE_CONTENT_NAMESPACES), not just
    // its nav label, so any word visible on that page surfaces it.
    const pageIndex = useMemo(
        () =>
            [...NAV_ITEMS, ...(extraNavItems ?? [])]
                .filter((item) => !item.permission || can(item.permission))
                .map((item) => {
                    const label = resolveLabel(item.label);
                    const namespaces = PAGE_CONTENT_NAMESPACES[item.to] ?? [];
                    const haystack = [label, ...namespaces.map((ns) => namespaceSearchText(ns, chromeLanguage))]
                        .join(" ")
                        .toLowerCase();
                    return {
                        result: { kind: "page", to: item.to, label, icon: item.icon ?? ROUTE_ICONS[item.to] } as Result,
                        haystack,
                    };
                }),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [chromeLanguage, can, extraNavItems]
    );

    const filteredPages = useMemo(() => {
        if (!q) return pageIndex.map(({ result }) => result);
        return pageIndex.filter(({ haystack }) => haystack.includes(q)).map(({ result }) => result);
    }, [pageIndex, q]);

    // Same {result, haystack} precompute as pageIndex above. Each item's
    // haystack folds in its `scope` sweep (every string under the given
    // dot-paths, e.g. every field/button/helper-text on the Change Password
    // tab) plus any one-off `matchKeys`, so any rendered word finds it.
    const contentIndex = useMemo(
        () =>
            [...SEARCH_ITEMS, ...(extraSearchItems ?? [])]
                .filter((item) => !item.permission || can(item.permission))
                .map((item) => {
                    const label = resolveLabel(item.label);
                    const group = resolveLabel(item.group);
                    const detail = item.detail ? resolveLabel(item.detail) : undefined;
                    const scopeText = item.scope ? scopedSearchText(item.scope.namespace, chromeLanguage, item.scope.paths) : "";
                    const haystack = [label, detail, group, scopeText, ...(item.matchKeys ?? []).map(resolveLabel)]
                        .join(" ")
                        .toLowerCase();
                    return {
                        result: {
                            kind: "content",
                            to: item.to,
                            label,
                            sublabel: detail ? `${group} · ${detail}` : group,
                            icon: item.icon,
                        } as Result,
                        haystack,
                    };
                }),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [chromeLanguage, can, extraSearchItems]
    );

    // Content results only surface once there's a query - unlike pages, the
    // full built-in list would otherwise dump extra rows into the palette's
    // default empty-query view.
    const filteredContent = useMemo(() => {
        if (!q) return [];
        return contentIndex.filter(({ haystack }) => haystack.includes(q)).map(({ result }) => result);
    }, [contentIndex, q]);

    // Ctrl+F-style results: every distinct string across all pages that
    // contains the query, each as its own row (not collapsed into one row
    // per page/feature like above). Sweeps the same sources. Deduped by
    // (destination, text) since strings can legitimately repeat, and capped
    // so a common word doesn't dump dozens of rows.
    const textMatches = useMemo(() => {
        if (!q) return [];
        const seen = new Set<string>();
        const results: Result[] = [];
        const pushMatch = (to: string, text: string, sublabel: string, icon?: React.ElementType) => {
            const key = `${to} ${text}`;
            if (seen.has(key)) return;
            seen.add(key);
            results.push({ kind: "match", to, label: text, sublabel, icon });
        };

        for (const item of [...NAV_ITEMS, ...(extraNavItems ?? [])]) {
            if (item.permission && !can(item.permission)) continue;
            const namespaces = PAGE_CONTENT_NAMESPACES[item.to] ?? [];
            if (namespaces.length === 0) continue;
            const pageLabel = resolveLabel(item.label);
            const icon = item.icon ?? ROUTE_ICONS[item.to];
            for (const ns of namespaces) {
                for (const text of namespaceMatches(ns, chromeLanguage, q)) {
                    pushMatch(item.to, text, pageLabel, icon);
                }
            }
        }

        for (const item of [...SEARCH_ITEMS, ...(extraSearchItems ?? [])]) {
            if (item.permission && !can(item.permission)) continue;
            if (!item.scope) continue;
            const group = resolveLabel(item.group);
            for (const text of scopedMatches(item.scope.namespace, chromeLanguage, item.scope.paths, q)) {
                pushMatch(item.to, text, group, item.icon);
            }
        }

        return results.slice(0, TEXT_MATCH_RESULTS_LIMIT);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [q, chromeLanguage, can, extraNavItems, extraSearchItems]);

    // Permission catalog entries are backend data, not i18next copy, so no
    // namespace sweep sees them. Small and fixed (~20 entries), so it's
    // swept client-side rather than round-tripped per keystroke like
    // filteredUsers below.
    const canViewPermissions = can(PERMISSIONS.PERMISSIONS_READ);
    const { data: permissionCatalog } = usePermissionCatalogQuery(canViewPermissions);
    const permissionsPageLabel = useMemo(
        () => resolveLabel("layout:nav.permissions"),
        // resolveLabel is derived entirely from chromeLanguage and the fixed translation registry.
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [chromeLanguage]
    );

    const permissionMatches = useMemo(() => {
        if (!q || !canViewPermissions || !permissionCatalog) return [];
        const seen = new Set<string>();
        const results: Result[] = [];
        for (const entry of permissionCatalog) {
            const haystack = `${entry.action} ${entry.resource_type} ${entry.description}`.toLowerCase();
            if (!haystack.includes(q)) continue;
            const key = `${entry.action}:${entry.resource_type}`;
            if (seen.has(key)) continue;
            seen.add(key);
            results.push({
                kind: "match",
                to: `/permissions?search=${encodeURIComponent(entry.action)}`,
                label: `${entry.action} · ${entry.resource_type}`,
                sublabel: permissionsPageLabel,
                icon: KeyRound,
            });
        }
        return results.slice(0, TEXT_MATCH_RESULTS_LIMIT);
    }, [q, canViewPermissions, permissionCatalog, permissionsPageLabel]);

    // Users are real account data, matched server-side (same endpoint
    // UsersPage.tsx uses) rather than a locally-held list, gated on
    // users:list_all like the sidebar link itself.
    const canSearchUsers = can(PERMISSIONS.USERS_LIST_ALL);
    const { data: userResults } = useUsersQuery(
        1,
        USER_RESULTS_LIMIT,
        { search: trimmedQuery },
        canSearchUsers && trimmedQuery.length > 0
    );

    const filteredUsers = useMemo(
        () =>
            (canSearchUsers && trimmedQuery ? userResults?.users ?? [] : []).map(
                (u): Result => ({
                    kind: "user",
                    to: `/users?search=${encodeURIComponent(u.email)}`,
                    label: u.name,
                    sublabel: u.email,
                    icon: Users,
                })
            ),
        [canSearchUsers, trimmedQuery, userResults]
    );

    // Policies are live backend data and must be gated by the same PBAC
    // permission as the Policies page. The backend remains authoritative for
    // the search result and only a small page is requested per query.
    const canSearchPolicies = can(PERMISSIONS.POLICIES_READ);
    const { data: policyResults } = usePoliciesListQuery(
        1,
        POLICY_RESULTS_LIMIT,
        { search: trimmedQuery, sortBy: "name", sortDir: "asc" },
        canSearchPolicies && trimmedQuery.length > 0
    );
    const policiesPageLabel = useMemo(
        () => resolveLabel("layout:nav.policies"),
        // resolveLabel is derived entirely from chromeLanguage and the fixed translation registry.
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [chromeLanguage]
    );

    const filteredPolicies = useMemo(
        () =>
            (canSearchPolicies && trimmedQuery ? policyResults?.policies ?? [] : []).map(
                (policy): Result => ({
                    kind: "policy",
                    to: `/policies?search=${encodeURIComponent(policy.name)}`,
                    label: policy.name,
                    sublabel: policy.description || policiesPageLabel,
                    icon: ShieldCheck,
                })
            ),
        [canSearchPolicies, policiesPageLabel, policyResults, trimmedQuery]
    );

    const filtered = useMemo(() => {
        const candidates = [
            ...filteredPages,
            ...filteredContent,
            ...textMatches,
            ...permissionMatches,
            ...filteredPolicies,
            ...filteredUsers,
        ];
        const kindPriority: Record<ResultKind, number> = {
            page: 0,
            content: 1,
            match: 2,
            policy: 3,
            user: 4,
        };

        // A page can match because any word in its full namespace matches the
        // query. That broad recall is useful, but it should not outrank a
        // feature whose visible label directly matches the query (e.g.
        // "Security events" should appear before Dashboard when searching
        // "secur"). Keep exact/label matches first, then fall back to
        // subtitles and finally broad page-content matches.
        const ranked = candidates
            .map((result, index) => {
                const label = result.label.toLowerCase();
                const sublabel = result.sublabel?.toLowerCase() ?? "";
                const relevance = label === q
                    ? 0
                    : label.startsWith(q)
                        ? 1
                        : label.includes(q)
                            ? 2
                            : sublabel.includes(q)
                                ? 3
                                : 4;
                return { result, relevance, index };
            })
        const groups = new Map<ResultKind, typeof ranked>();
        for (const item of ranked) {
            const group = groups.get(item.result.kind) ?? [];
            group.push(item);
            groups.set(item.result.kind, group);
        }

        return [...groups.values()]
            .sort((a, b) =>
                Math.min(...a.map((item) => item.relevance))
                - Math.min(...b.map((item) => item.relevance))
                || kindPriority[a[0].result.kind] - kindPriority[b[0].result.kind]
            )
            .flatMap((group) =>
                group
                    .sort((a, b) => a.relevance - b.relevance || a.index - b.index)
                    .map(({ result }) => result)
            );
    }, [q, filteredPages, filteredContent, textMatches, permissionMatches, filteredPolicies, filteredUsers]);
    // Only worth a group header once there are two-plus kinds of result -
    // a lone "Pages" header over an all-pages list is just noise.
    const kindCount = useMemo(() => new Set(filtered.map((item) => item.kind)).size, [filtered]);

    return { filtered, kindCount };
}
