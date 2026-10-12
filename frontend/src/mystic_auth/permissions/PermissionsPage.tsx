import React, { useEffect, useMemo, useState } from "react";
import { KeyRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import PageContainer from "../ui/navigation/PageContainer";
import { Button } from "../ui/buttons/Button";
import ExpandCollapseAllButtons from "../ui/navigation/ExpandCollapseAllButtons";
import { useDebouncedValue } from "../ui/hooks/useDebouncedValue";
import { usePermissionCatalogQuery, usePermissionCatalogUsageQuery } from "../policies/queries/permissionQueries";
import { groupByResourceType } from "../policies/logic/effectiveGrants";
import { isDestructiveAction } from "../authorization/destructiveActions";
import PermissionsFilterBar, { ALL_VALUE, type PermissionQuickFilter } from "./PermissionsFilterBar";
import PermissionDetailsDialog from "./PermissionDetailsDialog";
import PermissionsStatsCard, { type PermissionStatTileKey } from "./PermissionsStatsCard";
import type { PermissionCatalogEntry, PermissionUsageEntry } from "../api/permissions_api";
import { usePermissionsUiStore } from "./permissionsUiStore";
import PermissionGroupList from "./PermissionGroupList";
import { createPermissionTableColumns } from "./permissionTableColumns";
import PermissionsGroupSkeleton from "./PermissionsGroupSkeleton";
import { isForbiddenError } from "../api/apiError";
import GlossaryHelp from "../ui/display/GlossaryHelp";

/**
 * PermissionsPage
 * ----------------------------
 * Read-only, browsable view of MysticAuth's built-in permission catalog
 * (backend: GET /authorization/permissions/catalog, see
 * authorization/permissions_catalog.py), plus who actually holds each
 * action (GET .../catalog/usage). Kept separate from PoliciesPage rather
 * than a tab on it: this is the built-in action reference developers define,
 * Policies are how authorized operators compose it. No create/edit/delete, since a
 * permission only means something once a backend route checks for it.
 *
 * Redesigned per design/permissions.html and
 * .project/permissions-page-review.md: a row of stat tiles (Actions,
 * Resource types, Destructive, Unused) that double as quick filters, a
 * catalog-built resource-type picker (fixes the review's bug #1: the old
 * filter used a hardcoded 5-type list, so a fork's own resource types
 * couldn't be selected), a quick-filter segmented control (Destructive/In a
 * policy/Direct grants/Unused, all backed by the usage query), and a "Held
 * by" column. Expand/Collapse all stay visible and merely disabled rather
 * than vanishing when nothing would change (bug #4), and Collapse all
 * actually works while a search/filter is forcing groups open (bug #3, see
 * isExpanded below).
 *
 * Grouped by resource_type into one collapsible card per type (a resource
 * can have anywhere from 1 action, security_audit, to 9, users - see the
 * Policy builder's own ragged-column problem), rather than one flat
 * alphabetical table: a caller answering "what can I grant against
 * `users`?" opens one card instead of scanning a long list for matching
 * rows. Cards start collapsed (a header + count only) so five resource
 * types' worth of actions don't all render open at once and turn the page
 * into one long scroll; a search or resource-type filter force-expands
 * every group with a match, same as the collapse-then-reveal pattern
 * elsewhere in the app (UserPoliciesDialog's expand/collapse). Unlike
 * PoliciesPage this stays entirely client-side and unpaginated - the whole
 * catalog is ~20 static rows (usePermissionCatalogQuery's long staleTime),
 * small enough that grouped cards are the whole "list" once collapsed.
 *
 * Reads an initial `?search=` query param the same way AuditLogPage reads
 * `?category=`/`?scope=`: CommandPaletteResults' catalog-entry matches link
 * here with the matched action so the page opens with it already shown.
 */
const PermissionsPage: React.FC = () => {
    const { t } = useTranslation(["permissions", "ui_text"]);

    const [searchParams] = useSearchParams();
    const uiStore = usePermissionsUiStore();
    // `?search=` is a one-shot deep-link override (CommandPalette's catalog-entry matches),
    // then whatever was last set here, then "" - see AccountSettingsPage's matching comment.
    const [search, setSearchState] = useState(() => searchParams.get("search") ?? uiStore.search);
    const setSearch = (value: string) => {
        setSearchState(value);
        uiStore.update({ search: value });
    };
    const debouncedSearch = useDebouncedValue(search);
    const resourceType = uiStore.resourceType;
    const setResourceType = (value: string) => uiStore.update({ resourceType: value });
    const quickFilter = uiStore.quickFilter;
    const setQuickFilter = (value: PermissionQuickFilter | ((prev: PermissionQuickFilter) => PermissionQuickFilter)) =>
        uiStore.update({ quickFilter: typeof value === "function" ? value(uiStore.quickFilter) : value });

    const { data: catalog, isLoading, isError, error: catalogError, refetch } = usePermissionCatalogQuery();
    const {
        data: usage,
        isLoading: isUsageLoading,
        isError: isUsageError,
        error: usageError,
        refetch: refetchUsage,
    } = usePermissionCatalogUsageQuery();
    const usageReady = !isUsageLoading && !isUsageError;
    const effectiveQuickFilter = usageReady || quickFilter === "all" || quickFilter === "destructive" ? quickFilter : "all";

    useEffect(() => {
        if (!usageReady && (quickFilter === "policy" || quickFilter === "direct" || quickFilter === "unused")) {
            uiStore.update({ quickFilter: "all" });
        }
    }, [quickFilter, uiStore, usageReady]);
    const usageByAction = useMemo(() => new Map((usage ?? []).map((u) => [u.action, u])), [usage]);
    const usageFor = (action: string): PermissionUsageEntry | undefined => usageByAction.get(action);

    const [viewingEntry, setViewingEntry] = useState<PermissionCatalogEntry | null>(null);

    // Manually-opened groups. While a search/filter is active every group
    // with a match auto-expands instead (see isExpanded below), independent
    // of this set, so clearing the search returns to whatever the caller
    // had manually opened rather than snapping everything back shut.
    const expandedTypes = new Set(uiStore.expandedTypes);
    const setExpandedTypes = (next: Set<string>) => uiStore.update({ expandedTypes: [...next] });
    const toggleTypeExpanded = (type: string) => {
        const next = new Set(expandedTypes);
        if (next.has(type)) next.delete(type);
        else next.add(type);
        setExpandedTypes(next);
    };

    const matchesQuickFilter = (entry: PermissionCatalogEntry): boolean => {
        if (effectiveQuickFilter === "all") return true;
        if (effectiveQuickFilter === "destructive") return isDestructiveAction(entry.action);
        const u = usageFor(entry.action);
        if (effectiveQuickFilter === "policy") return !!u && u.policies.length > 0;
        if (effectiveQuickFilter === "direct") return !!u && u.direct_grant_count > 0;
        // "unused": nobody holds it, directly or via a policy. Undefined
        // usage (still loading) doesn't count as unused - see the loading
        // guard below, which keeps the whole list from flashing "unused"
        // for everything before usage resolves.
        return !!u && u.total_user_count === 0;
    };

    const filtered = useMemo(() => {
        const query = debouncedSearch.trim().toLowerCase();
        return (catalog ?? [])
            .filter((entry) => {
                if (resourceType !== ALL_VALUE && entry.resource_type !== resourceType) return false;
                if (isUsageLoading && effectiveQuickFilter !== "all" && effectiveQuickFilter !== "destructive") return false;
                if (!matchesQuickFilter(entry)) return false;
                if (!query) return true;
                return (
                    entry.action.toLowerCase().includes(query) ||
                    entry.description.toLowerCase().includes(query) ||
                    entry.resource_type.toLowerCase().includes(query)
                );
            })
            .sort((a, b) => a.action.localeCompare(b.action));
        // eslint-disable-next-line react-hooks/exhaustive-deps -- matchesQuickFilter closes over effectiveQuickFilter/usageByAction, both already listed
    }, [catalog, debouncedSearch, resourceType, effectiveQuickFilter, usageByAction, isUsageLoading]);

    const groups = groupByResourceType(filtered);
    const hasSearchOrFilters = !!search || resourceType !== ALL_VALUE || effectiveQuickFilter !== "all";
    const clearAllFilters = () => {
        setSearch("");
        setResourceType(ALL_VALUE);
        setQuickFilter("all");
    };

    const allOpen = groups.size > 0 && [...groups.keys()].every((type) => expandedTypes.has(type) || hasSearchOrFilters);
    const noneOpen = expandedTypes.size === 0 && !hasSearchOrFilters;
    const expandAll = () => setExpandedTypes(new Set(groups.keys()));
    const collapseAll = () => setExpandedTypes(new Set());

    const quickFilterCounts = useMemo(() => {
        const base = catalog ?? [];
        const inType = resourceType === ALL_VALUE ? base : base.filter((e) => e.resource_type === resourceType);
        return {
            all: inType.length,
            destructive: inType.filter((e) => isDestructiveAction(e.action)).length,
            policy: inType.filter((e) => !!usageFor(e.action) && usageFor(e.action)!.policies.length > 0).length,
            direct: inType.filter((e) => !!usageFor(e.action) && usageFor(e.action)!.direct_grant_count > 0).length,
            unused: inType.filter((e) => !!usageFor(e.action) && usageFor(e.action)!.total_user_count === 0).length,
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps -- usageFor closes over usageByAction, which is already listed
    }, [catalog, resourceType, usageByAction]);

    const activeStatTile: PermissionStatTileKey | null =
        effectiveQuickFilter === "destructive" ? "destructive" : effectiveQuickFilter === "unused" ? "unused" : !hasSearchOrFilters ? "total" : null;

    const groupColumns = createPermissionTableColumns(t, usageFor, isUsageError, setViewingEntry);

    return (
        <PageContainer
            title={t("permissions:page.title")}
            icon={KeyRound}
            titleExtra={
                <GlossaryHelp
                    ariaLabel={t("permissions:page.glossaryAriaLabel")}
                    items={[
                        { term: t("permissions:page.glossary.action.term"), definition: t("permissions:page.glossary.action.definition") },
                        { term: t("permissions:page.glossary.resourceType.term"), definition: t("permissions:page.glossary.resourceType.definition") },
                        { term: t("permissions:page.glossary.destructive.term"), definition: t("permissions:page.glossary.destructive.definition") },
                        { term: t("permissions:page.glossary.heldBy.term"), definition: t("permissions:page.glossary.heldBy.definition") },
                    ]}
                />
            }
            description={t("permissions:page.description")}
            headerExtra={
                <div className="flex flex-col gap-4">
                    <PermissionsStatsCard
                        catalog={catalog}
                        usage={usage}
                        catalogLoading={isLoading}
                        catalogError={isError}
                        usageLoading={isUsageLoading}
                        usageError={isUsageError}
                        activeTile={activeStatTile}
                        onFilterTotal={clearAllFilters}
                        onFilterDestructive={() => setQuickFilter((v) => (v === "destructive" ? "all" : "destructive"))}
                        onFilterUnused={() => setQuickFilter((v) => (v === "unused" ? "all" : "unused"))}
                    />
                    <PermissionsFilterBar
                        search={search}
                        setSearch={setSearch}
                        resourceType={resourceType}
                        setResourceType={setResourceType}
                        quickFilter={effectiveQuickFilter}
                        setQuickFilter={setQuickFilter}
                        quickFilterCounts={quickFilterCounts}
                        catalog={catalog}
                        totalResults={filtered.length}
                        isError={isError}
                        usageLoading={isUsageLoading}
                        usageError={isUsageError}
                        onRetryUsage={() => refetchUsage()}
                        usageForbidden={isForbiddenError(usageError)}
                        onClearFilters={clearAllFilters}
                    />
                </div>
            }
        >
            {/* Full-width row above the groups (design/permissions.html's
                results-row), rather than PageContainer's `actions` slot:
                `actions` sits beside headerExtra in the same flex row,
                which would squeeze the how/stats cards above narrower than
                the page instead of letting them span it edge to edge.
                Stays visible and merely disabled rather than vanishing
                across loading/error/empty states (bug #4). */}
            <ExpandCollapseAllButtons
                onExpandAll={expandAll}
                onCollapseAll={collapseAll}
                expandDisabled={allOpen || groups.size === 0}
                collapseDisabled={noneOpen}
                className="flex items-center justify-end gap-2 mb-4"
            />
            {isLoading ? (
                <PermissionsGroupSkeleton label={t("ui_text:loading")} />
            ) : isError ? (
                <div className="flex flex-col items-center gap-3 py-10">
                    <span className="text-fg-muted">{t(isForbiddenError(catalogError) ? "permissions:page.catalogForbidden" : "permissions:page.failedToLoadPermissions")}</span>
                    <Button onClick={() => refetch()} variant="secondary">
                        {t("ui_text:retry")}
                    </Button>
                </div>
            ) : groups.size === 0 ? (
                // No second "Clear filters" button here: the filter bar
                // above already has an always-visible one (design.md:
                // controls stay visible/disabled, not duplicated), so this
                // empty state is just the explanatory text.
                <div className="flex flex-col items-center gap-3 py-10">
                    <span className="text-fg-muted">
                        {hasSearchOrFilters ? t("permissions:page.noPermissionsMatchFilters") : t("permissions:page.noPermissionsYet")}
                    </span>
                </div>
            ) : <PermissionGroupList
                groups={groups}
                expandedTypes={expandedTypes}
                hasSearchOrFilters={hasSearchOrFilters}
                isUsageError={isUsageError}
                usageFor={usageFor}
                columns={groupColumns}
                t={t}
                onToggle={toggleTypeExpanded}
            />}

            <PermissionDetailsDialog
                isOpen={!!viewingEntry}
                entry={viewingEntry}
                usage={viewingEntry ? usageFor(viewingEntry.action) : undefined}
                usageLoading={isUsageLoading}
                usageError={isUsageError}
                usageForbidden={isForbiddenError(usageError)}
                onRetryUsage={() => refetchUsage()}
                onClose={() => setViewingEntry(null)}
            />
        </PageContainer>
    );
};

export default PermissionsPage;
