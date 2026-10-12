import React, { useState } from "react";
import { ClipboardList } from "lucide-react";
import { useTranslation } from "react-i18next";

import DataTable from "../../ui/DataTable/DataTable";
import LoadingState from "../../ui/feedback/LoadingState";
import Pagination from "../../ui/navigation/Pagination";
import { Button } from "../../ui/buttons/Button";
import { useDebouncedValue } from "../../ui/hooks/useDebouncedValue";
import { nextSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { useAuthorizationAuditLogQuery } from "./authorizationLogQueries";
import { getAuthorizationColumns } from "./authorizationLogColumns";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "../../policies/policyCardHelpers";
import AuthorizationFilterBar from "./AuthorizationFilterBar";
import AuthorizationDetailsDrawer from "./AuthorizationDetailsDrawer";
import {
    ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor, useTimeRangeParams, timeRangeLabel,
    DEFAULT_TIME_RANGE, type TimeRangeState,
} from "../auditLogListConfig";
import type { FilterChip } from "../../ui/filters/FilterChips";
import { useLanguageStore } from "../../store/languageStore";
import { useAllAuthorizationLogUiStore } from "./authorizationLogUiStore";
import type { AuthorizationAuditLogEntryRead } from "../../api/audit_api";
import { isForbiddenError } from "../../api/apiError";

interface AllAuthorizationLogSectionProps {
    /** See AuthorizationFilterBar's docstring. */
    extraResourceTypes?: string[];
    extraActions?: string[];
}

/** "Authorization decisions" tab's "All users" sub-tab (policies:read only):
 * same shape as MyAuthorizationLogSection, plus a server-side email search. */
const AllAuthorizationLogSection: React.FC<AllAuthorizationLogSectionProps> = ({
    extraResourceTypes, extraActions,
}) => {
    const { t } = useTranslation(["audit_log", "ui_text"]);
    // chromeLanguage, not pageLanguage: the "when" column's dates should read like navbar/sidebar
    // chrome, not the mixed page-content language used for "en+hi"/"en+mr".
    // See languageStore.ts's LanguageMode docstring.
    const language = useLanguageStore((s) => s.chromeLanguage);
    // Backed by useAllAuthorizationLogUiStore - see AllSecurityLogSection's matching comment.
    const { search, action, resourceType, allowed, sortKey, sortDir, range, customFrom, customTo, update } =
        useAllAuthorizationLogUiStore();
    const timeRange: TimeRangeState = { range, customFrom, customTo };
    const setTimeRange = (next: TimeRangeState) => update(next);
    const setSearch = (value: string) => update({ search: value });
    const setAction = (value: string) => update({ action: value });
    const setResourceType = (value: string) => update({ resourceType: value });
    const setAllowed = (value: string) => update({ allowed: value });
    const sort = { key: sortKey, direction: sortDir };
    const toggleSort = (key: string) => {
        const next = nextSortState(sort, key);
        update({ sortKey: next.key, sortDir: next.direction });
    };
    const debouncedSearch = useDebouncedValue(search);
    const rangeParams = useTimeRangeParams(timeRange);
    const [page, setPage] = usePageResetOn(
        `${debouncedSearch}|${sort.key}|${sort.direction}|${action}|${resourceType}|${allowed}|${rangeParams.from}|${rangeParams.to}`
    );

    const { data, error, isFetching, isLoading, isError, isPlaceholderData } = useAuthorizationAuditLogQuery(page, PAGE_SIZE, {
        search: debouncedSearch,
        action: action || undefined,
        resourceType: resourceType || undefined,
        allowed: toBoolFilter(allowed),
        sortBy: sort.key,
        sortDir: sort.direction,
        from: rangeParams.from,
        to: rangeParams.to,
    });
    const totalPages = totalPagesFor(data?.total ?? 0);

    const [openGlobalIndex, setOpenGlobalIndex] = useState<number | null>(null);
    const [openEntry, setOpenEntry] = useState<AuthorizationAuditLogEntryRead | null>(null);
    const openPage = openGlobalIndex !== null ? Math.floor(openGlobalIndex / PAGE_SIZE) + 1 : null;
    const openRowIndex = openGlobalIndex !== null ? openGlobalIndex % PAGE_SIZE : null;
    const globalIndex = openGlobalIndex !== null ? openGlobalIndex + 1 : undefined;
    const drawerEntry =
        openGlobalIndex !== null && openPage === page && !isPlaceholderData && !isFetching
            ? (data?.rows[openRowIndex ?? -1] ?? openEntry)
            : openEntry;

    const hasNonRangeFilters = !!search || action !== ALL_VALUE || resourceType !== ALL_VALUE || allowed !== ALL_VALUE;
    const isRangeActive = range !== DEFAULT_TIME_RANGE || (range === "custom" && !!customFrom && !!customTo);
    const clearAll = () =>
        update({ search: "", action: ALL_VALUE, resourceType: ALL_VALUE, allowed: ALL_VALUE, range: DEFAULT_TIME_RANGE, customFrom: "", customTo: "" });
    const chips: FilterChip[] = [
        ...(isRangeActive
            ? [{ key: "range", label: timeRangeLabel(timeRange, t), onClear: () => setTimeRange({ range: DEFAULT_TIME_RANGE, customFrom: "", customTo: "" }) }]
            : []),
        ...(search ? [{ key: "search", label: search, onClear: () => setSearch("") }] : []),
        ...(action !== ALL_VALUE
                ? [{ key: "action", label: formatPolicyActionLabel(action), onClear: () => setAction(ALL_VALUE) }]
            : resourceType !== ALL_VALUE
                ? [{ key: "resourceType", label: formatResourceTypeLabel(resourceType), onClear: () => setResourceType(ALL_VALUE) }]
                : []),
        ...(allowed !== ALL_VALUE
            ? [{ key: "allowed", label: t(`authorization.results.${allowed === "true" ? "allowed" : "denied"}`), onClear: () => setAllowed(ALL_VALUE) }]
            : []),
    ];

    const isEmpty = !isLoading && !isError && (data?.rows.length ?? 0) === 0;
    // Two distinct empty states: a filter/search narrowed to zero (chips + Clear filters) vs.
    // the time range itself having nothing in it (a "Show last 90 days" shortcut) - see
    // .project/audit-log-design-review.md's "Two empty states".
    const showRangeEmpty = isEmpty && !hasNonRangeFilters;
    const emptyMessage = showRangeEmpty
        ? t("authorization.emptyRange", { days: rangeParams.days })
        : search
            ? t("authorization.emptySearch")
            : t("authorization.emptyFiltered");
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
            <AuthorizationFilterBar
                timeRange={timeRange} setTimeRange={setTimeRange}
                search={search} setSearch={setSearch} mine={false}
                action={action} setAction={setAction}
                resourceType={resourceType} setResourceType={setResourceType}
                allowed={allowed} setAllowed={setAllowed}
                chips={chips} onClearAll={clearAll}
                isFetching={isFetching} totalResults={data?.total}
                extraResourceTypes={extraResourceTypes}
                extraActions={extraActions}
            />
            {isLoading ? (
                <div className="flex min-h-64 items-center justify-center [scrollbar-gutter:stable]">
                    <LoadingState message={t("ui_text:loading")} />
                </div>
            ) : (
                <DataTable
                    columns={getAuthorizationColumns(t, language)}
                    rows={data?.rows}
                    rowKey={(e) => e.id}
                    isFetching={isFetching}
                    isError={isError}
                    errorMessage={isForbiddenError(error) ? t("authorization.forbidden") : undefined}
                    emptyMessage={emptyMessage}
                    emptyAction={emptyAction}
                    emptyIcon={<ClipboardList size={32} aria-hidden="true" />}
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
            <AuthorizationDetailsDrawer
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
                onFilterAction={(actionValue) => {
                    setAction(actionValue);
                    setOpenEntry(null);
                    setOpenGlobalIndex(null);
                }}
            />
        </>
    );
};

export default AllAuthorizationLogSection;
