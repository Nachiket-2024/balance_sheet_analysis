import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";

import StyledSelect from "../ui/filters/StyledSelect";
import SearchInput from "../ui/filters/SearchInput";
import GroupedSearchSelect, { type GroupedSearchOptionGroup } from "../ui/filters/GroupedSearchSelect";
import FilterChips, { type FilterChip } from "../ui/filters/FilterChips";
import FilterPanel from "../ui/cards/FilterPanel";
import { AUTHORIZATION_RESOURCE_TYPES } from "../audit_log/authorization_log/authorizationLogResourceTypes";
import { isDestructiveAction } from "../authorization/destructiveActions";
import type { PolicyRead } from "../api/policies_api";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "./policyCardHelpers";

export const ALL_VALUE = "";

interface PoliciesFilterBarProps {
    search: string;
    setSearch: (v: string) => void;
    resourceType: string;
    setResourceType: (v: string) => void;
    status: string;
    setStatus: (v: string) => void;
    /** "Which policies grant this action" - same GroupedSearchSelect pattern
     * as AuthorizationFilterBar's Action picker, grouped by resource type. */
    containsAction: string;
    setContainsAction: (v: string) => void;
    /** Every unfiltered policy - used to compute a per-resource-type count
     * and to build the resource type list, since it needs to include any
     * type a fork added even if the built-in catalog doesn't know about it. */
    allPolicies: PolicyRead[] | undefined;
    /** See UsersFilterBar's identical props for why: the search box's own
     * spinner/result-count hint. */
    isFetching: boolean;
    totalResults: number | undefined;
    /** Rendered next to the search input (e.g. Create Policy) so it reads as
     * a sibling action on the search row, not stranded at the page edge. */
    searchRowExtra?: React.ReactNode;
    destructiveOnly?: boolean;
    setDestructiveOnly?: (v: boolean) => void;
}

/** PoliciesPage's search box + resource type/status filters, split out like
 * UsersFilterBar.tsx and the audit_log FilterBars. Owns only the controls;
 * PoliciesPage owns the state and the server-side query they drive.
 *
 * Bug fix: the resource type list used to come from the fixed
 * AUTHORIZATION_RESOURCE_TYPES constant, so a fork-added resource type (e.g.
 * "invoices") could never be selected even though policies used it. It now
 * comes from the actual policy data, with the built-in types listed first. */
const PoliciesFilterBar: React.FC<PoliciesFilterBarProps> = ({
    search, setSearch, resourceType, setResourceType, status, setStatus,
    containsAction, setContainsAction, allPolicies, isFetching, totalResults, searchRowExtra, destructiveOnly = false, setDestructiveOnly,
}) => {
    const { t } = useTranslation(["policies", "ui_text"]);

    // Every action actually granted by some policy, grouped by its
    // resource-type prefix (e.g. "invoices:void" -> "invoices") - not
    // policy.resource_type, since a "*" policy like system_superuser grants
    // actions across many resource types at once.
    const actionGroups: GroupedSearchOptionGroup[] = useMemo(() => {
        const byResourceType = new Map<string, Set<string>>();
        for (const p of allPolicies ?? []) {
            for (const action of p.actions) {
                const rt = action.split(":")[0];
                if (!byResourceType.has(rt)) byResourceType.set(rt, new Set());
                byResourceType.get(rt)!.add(action);
            }
        }
        const coreTypes = AUTHORIZATION_RESOURCE_TYPES.filter((rt) => rt !== "*");
        const forkTypes = Array.from(byResourceType.keys()).filter((rt) => !coreTypes.includes(rt as never)).sort();
        return [...coreTypes, ...forkTypes]
            .map((rt) => ({
                key: rt,
                label: formatResourceTypeLabel(rt),
                options: Array.from(byResourceType.get(rt) ?? [])
                    .sort()
                    .map((a) => ({ value: a, label: formatPolicyActionLabel(a), destructive: isDestructiveAction(a) })),
            }))
            .filter((g) => g.options.length > 0);
    }, [allPolicies]);

    const resourceTypeOptions = useMemo(() => {
        const counts = new Map<string, number>();
        for (const p of allPolicies ?? []) {
            counts.set(p.resource_type, (counts.get(p.resource_type) ?? 0) + 1);
        }
        const coreTypes = AUTHORIZATION_RESOURCE_TYPES.filter((rt) => rt !== "*");
        const forkTypes = Array.from(counts.keys()).filter((rt) => !coreTypes.includes(rt as never)).sort();
        const label = (rt: string) => {
            const count = counts.get(rt);
            return count ? `${formatResourceTypeLabel(rt)} (${t("policies:page.resourceTypePolicyCount", { count })})` : formatResourceTypeLabel(rt);
        };
        return [
            { value: ALL_VALUE, label: t("policies:page.allResourceTypes") },
            ...coreTypes.map((rt) => ({ value: rt, label: label(rt) })),
            ...forkTypes.map((rt) => ({ value: rt, label: label(rt) })),
        ];
    }, [allPolicies, t]);

    const chips: FilterChip[] = [
        ...(search ? [{ key: "search", label: `Search: ${search}`, onClear: () => setSearch("") }] : []),
        ...(resourceType !== ALL_VALUE ? [{ key: "resource-type", label: `${t("policies:page.filterByResourceType")}: ${formatResourceTypeLabel(resourceType)}`, onClear: () => setResourceType(ALL_VALUE) }] : []),
        ...(status !== ALL_VALUE ? [{
            key: "status",
            label: status === "true" ? t("ui_text:active") : t("ui_text:inactive"),
            onClear: () => setStatus(ALL_VALUE),
        }] : []),
        ...(containsAction !== ALL_VALUE ? [{ key: "action", label: `${t("policies:page.filterByAction")}: ${formatPolicyActionLabel(containsAction)}`, onClear: () => setContainsAction(ALL_VALUE) }] : []),
        ...(destructiveOnly && setDestructiveOnly ? [{
            key: "destructive",
            label: t("policies:statsCard.destructive"),
            onClear: () => setDestructiveOnly(false),
        }] : []),
    ];
    const clearFilters = () => {
        setSearch("");
        setResourceType(ALL_VALUE);
        setStatus(ALL_VALUE);
        setContainsAction(ALL_VALUE);
        setDestructiveOnly?.(false);
    };

    return (
        <FilterPanel>
            <div className="flex items-center gap-3 flex-wrap">
                <SearchInput
                    placeholder={t("policies:page.searchPlaceholder")}
                    value={search}
                    onChange={setSearch}
                    isFetching={isFetching}
                    totalResults={totalResults}
                    resultsLabel={(count) => t("policies:page.resultsCount", { count })}
                    loadingLabel={t("ui_text:loading")}
                />

                <StyledSelect
                    className="w-52"
                    ariaLabel={t("policies:page.filterByResourceType")}
                    value={resourceType}
                    onChange={setResourceType}
                    isActive={resourceType !== ALL_VALUE}
                    options={resourceTypeOptions}
                />

                <StyledSelect
                    className="w-36"
                    ariaLabel={t("policies:page.filterByStatus")}
                    value={status}
                    onChange={setStatus}
                    isActive={status !== ALL_VALUE}
                    options={[
                        { value: ALL_VALUE, label: t("policies:page.allStatuses") },
                        { value: "true", label: t("ui_text:active") },
                        { value: "false", label: t("ui_text:inactive") },
                    ]}
                />

                <GroupedSearchSelect
                    className="w-56"
                    ariaLabel={t("policies:page.filterByAction")}
                    searchPlaceholder={t("policies:page.searchActions")}
                    value={containsAction}
                    onChange={setContainsAction}
                    allValue={ALL_VALUE}
                    allLabel={t("policies:page.allActions")}
                    isActive={containsAction !== ALL_VALUE}
                    groups={actionGroups}
                />

                {searchRowExtra}
            </div>

            <FilterChips chips={chips} onClearAll={clearFilters} />
        </FilterPanel>
    );
};

export default PoliciesFilterBar;
