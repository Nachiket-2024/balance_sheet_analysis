import React from "react";
import { useTranslation } from "react-i18next";

import StyledSelect from "../ui/filters/StyledSelect";
import SearchInput from "../ui/filters/SearchInput";
import QuickFilterSegment, { type QuickFilterOption } from "../ui/filters/QuickFilterSegment";
import FilterChips, { type FilterChip } from "../ui/filters/FilterChips";
import FormAlert from "../ui/feedback/FormAlert";
import { Button } from "../ui/buttons/Button";
import type { PermissionCatalogEntry } from "../api/permissions_api";
import { formatResourceTypeLabel } from "../policies/policyCardHelpers";

export const ALL_VALUE = "";

export type PermissionQuickFilter = "all" | "destructive" | "policy" | "direct" | "unused";

interface PermissionsFilterBarProps {
    search: string;
    setSearch: (v: string) => void;
    resourceType: string;
    setResourceType: (v: string) => void;
    quickFilter: PermissionQuickFilter;
    setQuickFilter: (v: PermissionQuickFilter) => void;
    quickFilterCounts: Record<PermissionQuickFilter, number>;
    /** Built from the loaded catalog, not a hardcoded resource-type list -
     * fixes .project/permissions-page-review.md bug #1 (a fork adding its
     * own resource type couldn't be selected at all). Undefined while the
     * catalog is still loading. */
    catalog: PermissionCatalogEntry[] | undefined;
    totalResults: number;
    isError: boolean;
    usageLoading: boolean;
    usageError: boolean;
    usageForbidden: boolean;
    onRetryUsage: () => void;
    onClearFilters: () => void;
}

/** PermissionsPage's search box, resource-type picker, and quick-filter
 * segmented control (design/permissions.html). Same search+select pattern
 * as PoliciesFilterBar, with the quick filter kept in the primary control row and an
 * always-visible "Clear filters" button (design.md: controls stay visible
 * and disabled rather than appearing/disappearing based on state). */
const PermissionsFilterBar: React.FC<PermissionsFilterBarProps> = ({
    search, setSearch, resourceType, setResourceType, quickFilter, setQuickFilter, quickFilterCounts,
    catalog, totalResults, isError, usageLoading, usageError, usageForbidden, onRetryUsage, onClearFilters,
}) => {
    const { t } = useTranslation(["permissions", "ui_text"]);

    const resourceTypeCounts = new Map<string, number>();
    for (const entry of catalog ?? []) {
        resourceTypeCounts.set(entry.resource_type, (resourceTypeCounts.get(entry.resource_type) ?? 0) + 1);
    }
    const resourceTypeOptions = [...resourceTypeCounts.keys()].sort();

    const quickFilters: QuickFilterOption[] = [
        { value: "all", label: t("permissions:page.quickFilters.all"), count: quickFilterCounts.all },
        {
            value: "destructive",
            label: t("permissions:page.quickFilters.destructive"),
            count: quickFilterCounts.destructive,
            danger: true,
        },
        {
            value: "policy",
            label: t("permissions:page.quickFilters.policy"),
            count: usageLoading || usageError ? "–" : quickFilterCounts.policy,
            disabled: usageLoading || usageError,
        },
        {
            value: "direct",
            label: t("permissions:page.quickFilters.direct"),
            count: usageLoading || usageError ? "–" : quickFilterCounts.direct,
            disabled: usageLoading || usageError,
        },
        {
            value: "unused",
            label: t("permissions:page.quickFilters.unused"),
            count: usageLoading || usageError ? "–" : quickFilterCounts.unused,
            disabled: usageLoading || usageError,
        },
    ];
    const chips: FilterChip[] = [
        ...(search ? [{ key: "search", label: t("permissions:page.filterChipSearch", { value: search }), onClear: () => setSearch("") }] : []),
        ...(resourceType !== ALL_VALUE ? [{ key: "resource-type", label: t("permissions:page.filterChipResourceType", { value: formatResourceTypeLabel(resourceType) }), onClear: () => setResourceType(ALL_VALUE) }] : []),
        ...(quickFilter !== "all" ? [{
            key: "quick-filter",
            label: quickFilters.find((filter) => filter.value === quickFilter)?.label ?? quickFilter,
            onClear: () => setQuickFilter("all"),
        }] : []),
    ];

    return (
        <div className="flex flex-col gap-3 rounded-2xl border border-border-card bg-bg-surface/70 p-3 shadow-card sm:p-4">
            {usageError && (
                <FormAlert status="warning">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <p>{t(usageForbidden ? "permissions:page.holderInfoForbiddenTitle" : "permissions:page.holderInfoErrorTitle")}</p>
                            <p className="font-normal">{t(usageForbidden ? "permissions:page.holderInfoForbiddenDescription" : "permissions:page.holderInfoErrorDescription")}</p>
                        </div>
                        <Button type="button" variant="secondary" size="sm" onClick={onRetryUsage}>
                            {t("permissions:page.retryHolderInfo")}
                        </Button>
                    </div>
                </FormAlert>
            )}
            <div className="flex items-center gap-3 flex-wrap">
                <SearchInput
                    placeholder={t("permissions:page.searchPlaceholder")}
                    value={search}
                    onChange={setSearch}
                    totalResults={totalResults}
                    resultsLabel={(count) => t("permissions:page.resultsCount", { count })}
                    loadingLabel={t("ui_text:loading")}
                    disabled={isError}
                />
                <StyledSelect
                    className="w-52"
                    ariaLabel={t("permissions:page.filterByResourceType")}
                    value={resourceType}
                    onChange={setResourceType}
                    isActive={resourceType !== ALL_VALUE}
                    disabled={isError}
                    options={[
                        { value: ALL_VALUE, label: t("permissions:page.allResourceTypes") },
                        ...resourceTypeOptions.map((value) => ({
                            value,
                            label: `${formatResourceTypeLabel(value)} (${resourceTypeCounts.get(value)})`,
                        })),
                    ]}
                />
                <QuickFilterSegment
                    value={quickFilter}
                    options={quickFilters}
                    ariaLabel={t("permissions:page.quickFilterLabel")}
                    disabled={isError}
                    onChange={(next) => setQuickFilter(quickFilter === next ? "all" : next as PermissionQuickFilter)}
                />
            </div>

            <FilterChips chips={isError ? [] : chips} onClearAll={onClearFilters} />
        </div>
    );
};

export default PermissionsFilterBar;
