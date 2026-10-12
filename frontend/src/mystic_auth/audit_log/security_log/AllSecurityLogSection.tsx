import React, { useState } from "react";
import { History } from "lucide-react";
import { useTranslation } from "react-i18next";

import Card from "../../ui/cards/Card";
import SectionHeading from "../../ui/navigation/SectionHeading";
import DataTable from "../../ui/DataTable/DataTable";
import LoadingState from "../../ui/feedback/LoadingState";
import Pagination from "../../ui/navigation/Pagination";
import { Button } from "../../ui/buttons/Button";
import { useDebouncedValue } from "../../ui/hooks/useDebouncedValue";
import { nextSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { useSecurityAuditLogQuery, useLoginTrendQuery } from "./securityLogQueries";
import { getSecurityColumns } from "./securityLogColumns";
import SecurityFilterBar from "./SecurityFilterBar";
import LoginTrendChart from "./LoginTrendChart";
import SecurityDetailsDrawer from "./SecurityDetailsDrawer";
import {
    ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor, useTimeRangeParams, timeRangeLabel,
    DEFAULT_TIME_RANGE, type TimeRangeState,
} from "../auditLogListConfig";
import type { FilterChip } from "../../ui/filters/FilterChips";
import { useLanguageStore } from "../../store/languageStore";
import { useAllSecurityLogUiStore } from "./securityLogUiStore";
import type { SecurityAuditLogEntryRead } from "../../api/audit_api";
import { isForbiddenError } from "../../api/apiError";
import { humanizeSecurityEventType } from "./securityLogEventTypes";

// Same reasoning as AllAuthorizationLogSection.tsx.
const AllSecurityLogSection: React.FC = () => {
    const { t } = useTranslation(["audit_log", "ui_text"]);
    // See AllAuthorizationLogSection.tsx's matching comment: dates use chromeLanguage, not
    // pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    // Backed by useAllSecurityLogUiStore, not local useState, so these filters survive
    // leaving this sub-tab (or the page) and coming back - see securityLogUiStore.ts.
    const { search, eventType, ipAddress, success, sortKey, sortDir, range, customFrom, customTo, update } =
        useAllSecurityLogUiStore();
    const timeRange: TimeRangeState = { range, customFrom, customTo };
    const setTimeRange = (next: TimeRangeState) => update(next);
    const setSearch = (value: string) => update({ search: value });
    const setEventType = (value: string) => update({ eventType: value });
    const setIpAddress = (value: string) => update({ ipAddress: value });
    const setSuccess = (value: string) => update({ success: value });
    const sort = { key: sortKey, direction: sortDir };
    const toggleSort = (key: string) => {
        const next = nextSortState(sort, key);
        update({ sortKey: next.key, sortDir: next.direction });
    };
    const debouncedSearch = useDebouncedValue(search);
    const debouncedIpAddress = useDebouncedValue(ipAddress);
    const rangeParams = useTimeRangeParams(timeRange);
    const [page, setPage] = usePageResetOn(
        `${debouncedSearch}|${sort.key}|${sort.direction}|${eventType}|${debouncedIpAddress}|${success}|${rangeParams.from}|${rangeParams.to}`
    );

    const { data, error, isFetching, isLoading, isError, isPlaceholderData } = useSecurityAuditLogQuery(page, PAGE_SIZE, {
        search: debouncedSearch,
        eventType: eventType || undefined,
        ipAddress: debouncedIpAddress || undefined,
        success: toBoolFilter(success),
        sortBy: sort.key,
        sortDir: sort.direction,
        from: rangeParams.from,
        to: rangeParams.to,
    });
    const totalPages = totalPagesFor(data?.total ?? 0);
    // The chart and table use the same exact inclusive bounds.
    const trend = useLoginTrendQuery(rangeParams.days, debouncedSearch, rangeParams.from, rangeParams.to);

    const [openGlobalIndex, setOpenGlobalIndex] = useState<number | null>(null);
    const [openEntry, setOpenEntry] = useState<SecurityAuditLogEntryRead | null>(null);
    const openPage = openGlobalIndex !== null ? Math.floor(openGlobalIndex / PAGE_SIZE) + 1 : null;
    const openRowIndex = openGlobalIndex !== null ? openGlobalIndex % PAGE_SIZE : null;
    const globalIndex = openGlobalIndex !== null ? openGlobalIndex + 1 : undefined;
    const drawerEntry =
        openGlobalIndex !== null && openPage === page && !isPlaceholderData && !isFetching
            ? (data?.rows[openRowIndex ?? -1] ?? openEntry)
            : openEntry;

    const hasNonRangeFilters = !!search || eventType !== ALL_VALUE || !!ipAddress || success !== ALL_VALUE;
    const isRangeActive = range !== DEFAULT_TIME_RANGE || (range === "custom" && !!customFrom && !!customTo);
    const clearAll = () =>
        update({ search: "", eventType: ALL_VALUE, ipAddress: "", success: ALL_VALUE, range: DEFAULT_TIME_RANGE, customFrom: "", customTo: "" });
    const chips: FilterChip[] = [
        ...(isRangeActive
            ? [{ key: "range", label: timeRangeLabel(timeRange, t), onClear: () => setTimeRange({ range: DEFAULT_TIME_RANGE, customFrom: "", customTo: "" }) }]
            : []),
        ...(search ? [{ key: "search", label: search, onClear: () => setSearch("") }] : []),
        ...(eventType !== ALL_VALUE ? [{ key: "eventType", label: t(`security.filterBar.eventLabels.${eventType}`, { defaultValue: humanizeSecurityEventType(eventType) }), onClear: () => setEventType(ALL_VALUE) }] : []),
        ...(ipAddress ? [{ key: "ip", label: ipAddress, onClear: () => setIpAddress("") }] : []),
        ...(success !== ALL_VALUE
            ? [{ key: "success", label: t(`security.results.${success === "true" ? "success" : "failed"}`), onClear: () => setSuccess(ALL_VALUE) }]
            : []),
    ];

    const isEmpty = !isLoading && !isError && (data?.rows.length ?? 0) === 0;
    const showRangeEmpty = isEmpty && !hasNonRangeFilters;
    const emptyMessage = showRangeEmpty
        ? t("security.emptyRange", { days: rangeParams.days })
        : search
            ? t("security.emptySearch")
            : t("security.emptyFiltered");
    const emptyAction = showRangeEmpty
        ? rangeParams.days < 90 && (
            <Button type="button" size="sm" onClick={() => setTimeRange({ range: "90", customFrom: "", customTo: "" })}>
                {t("shared.showLast90Days")}
            </Button>
        )
        : hasNonRangeFilters && (
            <Button type="button" variant="outline" size="sm" onClick={clearAll}>
                {t("shared.clearFilters")}
            </Button>
        );

    return (
        <>
            <Card className="p-4 mb-4">
                <SectionHeading level="subsection" as="h3" className="mb-1">{t("security.signInActivity")}</SectionHeading>
                <p className="mb-3 text-sm text-fg-muted">{t("security.signInActivityDescription")}</p>
                <LoginTrendChart
                    data={trend.data}
                    isLoading={trend.isLoading}
                    isFetching={trend.isFetching}
                    isError={trend.isError}
                    errorMessage={isForbiddenError(trend.error) ? t("security.forbidden") : undefined}
                />
            </Card>
            <SecurityFilterBar
                timeRange={timeRange} setTimeRange={setTimeRange}
                search={search} setSearch={setSearch} mine={false}
                eventType={eventType} setEventType={setEventType}
                ipAddress={ipAddress} setIpAddress={setIpAddress}
                success={success} setSuccess={setSuccess}
                chips={chips} onClearAll={clearAll}
                isFetching={isFetching}
                totalResults={data?.total}
            />
            {isLoading ? (
                <div className="flex min-h-64 items-center justify-center [scrollbar-gutter:stable]">
                    <LoadingState message={t("ui_text:loading")} />
                </div>
            ) : (
                <DataTable
                    columns={getSecurityColumns(t, language)}
                    rows={data?.rows}
                    rowKey={(e) => e.id}
                    isFetching={isFetching}
                    isError={isError}
                    errorMessage={isForbiddenError(error) ? t("security.forbidden") : undefined}
                    emptyMessage={emptyMessage}
                    emptyAction={emptyAction}
                    emptyIcon={<History size={32} aria-hidden="true" />}
                    sort={sort}
                    onSortChange={toggleSort}
                    startIndex={(page - 1) * PAGE_SIZE}
                    onRowClick={(row) => {
                        const rowIndex = data?.rows.findIndex((r) => r.id === row.id) ?? -1;
                        if (rowIndex < 0) return;
                        setOpenEntry(row);
                        setOpenGlobalIndex((page - 1) * PAGE_SIZE + rowIndex);
                    }}
                    activeRowKey={drawerEntry?.id}
                />
            )}
            {!isLoading && !isError && (data?.rows.length ?? 0) > 0 && (
                <Pagination page={page} totalPages={totalPages} onPageChange={setPage} className="mt-4" />
            )}
            <SecurityDetailsDrawer
                entry={drawerEntry}
                onClose={() => {
                    setOpenEntry(null);
                    setOpenGlobalIndex(null);
                }}
                index={globalIndex}
                total={data?.total}
                onPrevious={() => {
                    if (openGlobalIndex === null || openGlobalIndex <= 0) return;
                    const nextIndex = openGlobalIndex - 1;
                    setOpenGlobalIndex(nextIndex);
                    const nextPage = Math.floor(nextIndex / PAGE_SIZE) + 1;
                    if (nextPage !== page) setPage(nextPage);
                    else setOpenEntry(data?.rows[nextIndex % PAGE_SIZE] ?? openEntry);
                }}
                onNext={() => {
                    if (openGlobalIndex === null || !data || openGlobalIndex >= data.total - 1) return;
                    const nextIndex = openGlobalIndex + 1;
                    setOpenGlobalIndex(nextIndex);
                    const nextPage = Math.floor(nextIndex / PAGE_SIZE) + 1;
                    if (nextPage !== page) setPage(nextPage);
                    else setOpenEntry(data.rows[nextIndex % PAGE_SIZE] ?? openEntry);
                }}
                canGoPrevious={openGlobalIndex !== null && openGlobalIndex > 0}
                canGoNext={openGlobalIndex !== null && !!data && openGlobalIndex < data.total - 1}
                language={language}
                onFilterUser={(email) => {
                    setSearch(email);
                    setOpenEntry(null);
                    setOpenGlobalIndex(null);
                }}
                onFilterIp={(ip) => {
                    setIpAddress(ip);
                    setOpenEntry(null);
                    setOpenGlobalIndex(null);
                }}
                onFilterEvent={(eventType) => {
                    setEventType(eventType);
                    setOpenEntry(null);
                    setOpenGlobalIndex(null);
                }}
            />
        </>
    );
};

export default AllSecurityLogSection;
