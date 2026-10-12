import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";

import SegmentedControl from "../../ui/filters/SegmentedControl";
import GroupedSearchSelect, { type GroupedSearchOptionGroup } from "../../ui/filters/GroupedSearchSelect";
import SearchInput from "../../ui/filters/SearchInput";
import AppTooltip from "../../ui/feedback/AppTooltip";
import TimeRangeControl from "../../ui/filters/TimeRangeControl";
import FilterChips, { type FilterChip } from "../../ui/filters/FilterChips";
import { isDestructiveAction } from "../../authorization/destructiveActions";
import { PERMISSIONS } from "../../authorization/permissions";
import { AUTHORIZATION_RESOURCE_TYPES } from "./authorizationLogResourceTypes";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "../../policies/policyCardHelpers";
import { ALL_VALUE, type TimeRangeState } from "../auditLogListConfig";

interface AuthorizationFilterBarProps {
    timeRange: TimeRangeState;
    setTimeRange: (v: TimeRangeState) => void;
    search: string;
    setSearch: (v: string) => void;
    /** True on "My activity": the search box stays visible but disabled, with a tooltip
     * explaining why (already scoped to one user) - design/audit-log.html's search field. */
    mine: boolean;
    action: string;
    setAction: (v: string) => void;
    resourceType: string;
    setResourceType: (v: string) => void;
    allowed: string;
    setAllowed: (v: string) => void;
    chips: FilterChip[];
    onClearAll: () => void;
    /** See SearchInput's identical props: the search box's own spinner/result-count hint. */
    isFetching: boolean;
    totalResults: number | undefined;
    /**
     * Resource types beyond this app's own AUTHORIZATION_RESOURCE_TYPES, for downstream
     * projects that extend the PBAC resource vocabulary (see authorizationLogResourceTypes.ts).
     * Appended after the built-ins; omitting it leaves the dropdown unchanged.
     */
    extraResourceTypes?: string[];
    /** Same idea as extraResourceTypes, for actions beyond PERMISSIONS. */
    extraActions?: string[];
}

/**
 * Time range, search, Action/Resource, Result, then active-filter chips and Clear filters - one
 * row, filters that scope everything below them (the table, and on the security side the
 * chart), matching design/audit-log.html. Action is grouped by resource type in a searchable
 * picker (GroupedSearchSelect) instead of a flat list, since PERMISSIONS already runs past 20
 * values and only grows with fork-added actions. Clicking a group's header sets the Resource
 * filter for that whole type (and clears any single-action filter), which is why there's no
 * separate Resource dropdown next to it - the group header already covers that. Result is a
 * one-click segmented control (SegmentedControl) rather than open-then-pick.
 */
const AuthorizationFilterBar: React.FC<AuthorizationFilterBarProps> = ({
    timeRange, setTimeRange, search, setSearch, mine,
    action, setAction, resourceType, setResourceType, allowed, setAllowed,
    chips, onClearAll, isFetching, totalResults,
    extraResourceTypes, extraActions,
}) => {
    const { t } = useTranslation(["audit_log", "ui_text"]);

    const actionGroups: GroupedSearchOptionGroup[] = useMemo(() => {
        const allActions = [...Object.values(PERMISSIONS), ...(extraActions ?? [])];
        const resourceTypes = [...AUTHORIZATION_RESOURCE_TYPES, ...(extraResourceTypes ?? [])];
        return resourceTypes
            .map((rt) => ({
                key: rt,
                label: formatResourceTypeLabel(rt),
                options: allActions
                    .filter((a) => a.startsWith(`${rt}:`))
                    .map((a) => ({ value: a, label: formatPolicyActionLabel(a), destructive: isDestructiveAction(a) })),
            }))
            .filter((g) => g.options.length > 0);
    }, [extraActions, extraResourceTypes]);

    const allActionsLabel =
        resourceType !== ALL_VALUE
            ? t("authorization.filterBar.allActionsForResource", { resource: formatResourceTypeLabel(resourceType) })
            : t("authorization.filterBar.allActions");

    const searchBox = (
        <SearchInput
            placeholder={t("authorization.searchPlaceholder")}
            aria-label={t("authorization.searchPlaceholder")}
            value={mine ? "" : search}
            onChange={setSearch}
            size="sm"
            disabled={mine}
            isFetching={isFetching}
            totalResults={totalResults}
            resultsLabel={(count) => t("authorization.resultsCount", { count })}
            loadingLabel={t("ui_text:loading")}
        />
    );

    return (
        <div className="flex flex-col gap-3 mb-4 rounded-[var(--radius-card)] border border-border-default bg-bg-surface/60 p-3 shadow-sm">
            <div className="flex items-center gap-3 flex-wrap">
                <TimeRangeControl value={timeRange} onChange={setTimeRange} />

                {mine ? <AppTooltip content={t("shared.searchDisabledMine")}>{searchBox}</AppTooltip> : searchBox}

            </div>

            <div className="flex items-center gap-3 flex-wrap">
                <GroupedSearchSelect
                    className="w-64"
                    ariaLabel={t("authorization.filterBar.filterByAction")}
                    searchPlaceholder={t("authorization.filterBar.searchActions")}
                    value={action}
                    onChange={setAction}
                    allValue={ALL_VALUE}
                    allLabel={allActionsLabel}
                    isActive={action !== ALL_VALUE || resourceType !== ALL_VALUE}
                    groups={actionGroups}
                    onSelectGroup={(groupKey) => {
                        setResourceType(groupKey);
                        setAction(ALL_VALUE);
                    }}
                />

                <SegmentedControl
                    ariaLabel={t("authorization.filterBar.filterByResult")}
                    value={allowed}
                    onChange={setAllowed}
                    isActive={allowed !== ALL_VALUE}
                    options={[
                        { value: ALL_VALUE, label: t("authorization.filterBar.allResults") },
                        { value: "true", label: t("authorization.results.allowed"), dotClassName: "bg-[var(--green-500)]" },
                        { value: "false", label: t("authorization.results.denied"), dotClassName: "bg-[var(--red-500)]" },
                    ]}
                />
            </div>

            <FilterChips chips={chips} onClearAll={onClearAll} />
        </div>
    );
};

export default AuthorizationFilterBar;
