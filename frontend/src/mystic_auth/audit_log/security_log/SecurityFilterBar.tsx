import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";

import SegmentedControl from "../../ui/filters/SegmentedControl";
import GroupedSearchSelect, { type GroupedSearchOptionGroup } from "../../ui/filters/GroupedSearchSelect";
import SearchInput from "../../ui/filters/SearchInput";
import AppTooltip from "../../ui/feedback/AppTooltip";
import TimeRangeControl from "../../ui/filters/TimeRangeControl";
import FilterChips, { type FilterChip } from "../../ui/filters/FilterChips";
import { SECURITY_EVENT_TYPE_GROUPS } from "./securityLogEventTypes";
import { ALL_VALUE, type TimeRangeState } from "../auditLogListConfig";

interface SecurityFilterBarProps {
    timeRange: TimeRangeState;
    setTimeRange: (v: TimeRangeState) => void;
    search: string;
    setSearch: (v: string) => void;
    /** See AuthorizationFilterBar's identical prop. */
    mine: boolean;
    eventType: string;
    setEventType: (v: string) => void;
    ipAddress: string;
    setIpAddress: (v: string) => void;
    success: string;
    setSuccess: (v: string) => void;
    chips: FilterChip[];
    onClearAll: () => void;
    /** See UsersFilterBar's identical props for why: the email search box's own
     * spinner/result-count hint (see AuthorizationFilterBar's matching search box). */
    isFetching: boolean;
    totalResults: number | undefined;
}

const SecurityFilterBar: React.FC<SecurityFilterBarProps> = ({
    timeRange, setTimeRange, search, setSearch, mine,
    eventType, setEventType, ipAddress, setIpAddress, success, setSuccess,
    chips, onClearAll, isFetching, totalResults,
}) => {
    const { t } = useTranslation(["audit_log", "ui_text"]);

    // Each option's label is the translated, human-readable event name, with the raw code as
    // its sublabel (GroupedSearchSelect renders that smaller, under the label) - a reader
    // unfamiliar with the raw event_type strings still gets a readable name, but the exact
    // code (what the table itself shows) stays visible too.
    const eventGroups: GroupedSearchOptionGroup[] = useMemo(
        () =>
            Object.entries(SECURITY_EVENT_TYPE_GROUPS).map(([groupKey, eventTypes]) => ({
                key: groupKey,
                label: t(`security.filterBar.eventGroups.${groupKey}`),
                options: eventTypes.map((value) => ({
                    value,
                    label: t(`security.filterBar.eventLabels.${value}`),
                    sublabel: value,
                })),
            })),
        [t]
    );

    const searchBox = (
        <SearchInput
            placeholder={t("security.searchPlaceholder")}
            aria-label={t("security.searchPlaceholder")}
            value={mine ? "" : search}
            onChange={setSearch}
            size="sm"
            disabled={mine}
            isFetching={isFetching}
            totalResults={totalResults}
            resultsLabel={(count) => t("security.resultsCount", { count })}
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
                    ariaLabel={t("security.filterBar.filterByEvent")}
                    searchPlaceholder={t("security.filterBar.searchEvents")}
                    value={eventType}
                    onChange={setEventType}
                    allValue={ALL_VALUE}
                    allLabel={t("security.filterBar.allEvents")}
                    isActive={eventType !== ALL_VALUE}
                    groups={eventGroups}
                />

                <SearchInput
                    placeholder={t("security.filterBar.filterByIpPlaceholder")}
                    aria-label={t("security.filterBar.filterByIpAddress")}
                    value={ipAddress}
                    onChange={setIpAddress}
                    className="w-40"
                    size="sm"
                    resultsLabel={(count) => t("security.resultsCount", { count })}
                    loadingLabel={t("ui_text:loading")}
                />

                <SegmentedControl
                    ariaLabel={t("security.filterBar.filterByResult")}
                    value={success}
                    onChange={setSuccess}
                    isActive={success !== ALL_VALUE}
                    options={[
                        { value: ALL_VALUE, label: t("security.filterBar.allResults") },
                        { value: "true", label: t("security.results.success"), dotClassName: "bg-[var(--green-500)]" },
                        { value: "false", label: t("security.results.failed"), dotClassName: "bg-[var(--red-500)]" },
                    ]}
                />
            </div>

            <FilterChips chips={chips} onClearAll={onClearAll} />
        </div>
    );
};

export default SecurityFilterBar;
