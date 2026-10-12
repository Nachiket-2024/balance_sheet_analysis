import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";

import SearchInput from "../ui/filters/SearchInput";
import GroupedSearchSelect, { type GroupedSearchOptionGroup } from "../ui/filters/GroupedSearchSelect";
import FilterPanel from "../ui/cards/FilterPanel";
import QuickFilterSegment, { type QuickFilterOption } from "../ui/filters/QuickFilterSegment";
import FilterChips, { type FilterChip } from "../ui/filters/FilterChips";
import { RATE_LIMIT_ENDPOINTS } from "./rateLimitEndpoints";

export const ALL_VALUE = "";

interface RateLimitsFilterBarProps {
    endpoint: string;
    setEndpoint: (v: string) => void;
    identifier: string;
    setIdentifier: (v: string) => void;
    scope: string;
    setScope: (v: string) => void;
    /** See UsersFilterBar's identical props for why: the identifier box's
     * own spinner/result-count hint. */
    isFetching: boolean;
    totalResults: number | undefined;
    totalCount: number;
    ipCount: number;
    accountCount: number;
}

/** Same shape as UsersFilterBar/audit_log's *FilterBar components: this owns
 * only the filter controls, RateLimitsPage owns the state and query.
 * `identifier` is a substring match (debounced, like audit_log's search
 * filters), but `endpoint` needs an exact match server-side, so it's a
 * dropdown over RATE_LIMIT_ENDPOINTS instead of free text (a free-text box
 * used to silently return zero rows unless you typed the exact internal id,
 * e.g. "login" not "Login"). Nothing to debounce there: it refetches once an
 * option is picked. */
const RateLimitsFilterBar: React.FC<RateLimitsFilterBarProps> = ({
    endpoint, setEndpoint, identifier, setIdentifier, scope, setScope, isFetching, totalResults, totalCount, ipCount, accountCount,
}) => {
    const { t } = useTranslation(["rate_limits", "ui_text"]);

    const endpointOptions = useMemo(
        () => [{ value: ALL_VALUE, label: t("page.allEndpoints") }, ...RATE_LIMIT_ENDPOINTS.map((e) => ({ value: e, label: e }))],
        [t]
    );
    const endpointGroups = useMemo<GroupedSearchOptionGroup[]>(
        () => [{ key: "endpoints", label: t("page.endpointColumn"), options: endpointOptions.slice(1) }],
        [endpointOptions, t]
    );
    const scopeOptions: QuickFilterOption[] = [
        { value: ALL_VALUE, label: t("page.allScopes"), count: totalCount },
        { value: "ip", label: t("page.scopeIp"), count: ipCount },
        { value: "account", label: t("page.scopeAccount"), count: accountCount },
    ];

    const chips: FilterChip[] = [
        ...(endpoint ? [{ key: "endpoint", label: `${t("page.endpointColumn")}: ${endpoint}`, onClear: () => setEndpoint(ALL_VALUE) }] : []),
        ...(identifier ? [{ key: "identifier", label: `${t("page.identifierColumn")}: ${identifier}`, onClear: () => setIdentifier("") }] : []),
        ...(scope ? [{ key: "scope", label: `${t("page.scopeColumn")}: ${scope === "ip" ? t("page.scopeIp") : scope === "account" ? t("page.scopeAccount") : t("page.scopeEmail")}`, onClear: () => setScope(ALL_VALUE) }] : []),
    ];

    return (
        <FilterPanel>
            <div className="flex items-center gap-3 flex-wrap">
                <GroupedSearchSelect
                    className="min-w-40 max-w-56"
                    ariaLabel={t("page.filterByEndpoint")}
                    searchPlaceholder={t("page.searchEndpoints")}
                    value={endpoint}
                    onChange={setEndpoint}
                    allValue={ALL_VALUE}
                    allLabel={t("page.allEndpoints")}
                    isActive={endpoint !== ALL_VALUE}
                    groups={endpointGroups}
                />

                <SearchInput
                    placeholder={t("page.identifierPlaceholder")}
                    aria-label={t("page.filterByIdentifier")}
                    value={identifier}
                    onChange={setIdentifier}
                    isFetching={isFetching}
                    totalResults={totalResults}
                    resultsLabel={(count) => t("page.resultsCount", { count })}
                    loadingLabel={t("ui_text:loading")}
                />
                <QuickFilterSegment
                    value={scope}
                    options={scopeOptions}
                    ariaLabel={t("page.filterByScope")}
                    onChange={(next) => setScope(scope === next ? ALL_VALUE : next)}
                />
            </div>
            <FilterChips
                chips={chips}
                onClearAll={() => {
                    setEndpoint(ALL_VALUE);
                    setIdentifier("");
                    setScope(ALL_VALUE);
                }}
            />
        </FilterPanel>
    );
};

export default RateLimitsFilterBar;
