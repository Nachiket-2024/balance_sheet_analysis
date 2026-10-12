import React, { useEffect, useRef, useState } from "react";
import { Gauge, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import PageContainer from "../ui/navigation/PageContainer";
import DataTable from "../ui/DataTable/DataTable";
import Pagination from "../ui/navigation/Pagination";
import ConfirmDialog from "../ui/feedback/ConfirmDialog";
import { toaster } from "../ui/toaster/toasterInstance";
import { useLanguageStore } from "../store/languageStore";
import { useDebouncedValue } from "../ui/hooks/useDebouncedValue";
import { nextSortState } from "../ui/hooks/useSortState";
import { usePageResetOn } from "../ui/hooks/usePageResetOn";
import { useRateLimitsQuery } from "./rateLimitsQueries";
import { useResetRateLimitMutation } from "./rateLimitsMutations";
import RateLimitsFilterBar from "./RateLimitsFilterBar";
import { buildRateLimitsColumns } from "./rateLimitsColumns";
import { totalPagesFor } from "./rateLimitsListConfig";
import type { RateLimitEntry } from "../api/rate_limits_api";
import { isForbiddenError } from "../api/apiError";
import { useRateLimitsUiStore } from "./rateLimitsUiStore";
import { useRateLimitsSummaryQuery } from "./rateLimitsSummaryQueries";
import RateLimitsStatsCard from "./RateLimitsStatsCard";

// Small enough that one page of rows fits a normal viewport without
// DataTable's inner scroll area kicking in (see DataTable.tsx's maxH).
const PAGE_SIZE = 10;

/**
 * RateLimitsPage
 * ----------------------------
 * Permission-protected view of live Valkey-backed rate-limit counters (see
 * rate_limiter_service.py), gated by rate_limits:read (resetting a counter
 * needs the separate rate_limits:reset action, see IfCan in
 * rateLimitsColumns.tsx). Numbered pagination like the audit log tables:
 * the backend walks the matching Valkey keyspace to compute a real total,
 * sorts the bounded snapshot, and slices out one page.
 */
const RateLimitsPage: React.FC = () => {
    const { t } = useTranslation("rate_limits");
    const language = useLanguageStore((s) => s.chromeLanguage);
    // Backed by useRateLimitsUiStore, not local useState, so these survive leaving this
    // page and coming back - see accountSettingsUiStore.ts's matching comment.
    const { endpoint, identifier, scope, sort, kind, update } = useRateLimitsUiStore();
    const setEndpoint = (value: string) => update({
        endpoint: value,
        kind: value === "login_lock" ? "login_lockouts" : kind === "login_lockouts" ? "all" : kind,
    });
    const setIdentifier = (value: string) => update({ identifier: value });
    const debouncedIdentifier = useDebouncedValue(identifier);
    const setScope = (value: string) => update({ scope: value });
    const toggleSort = (key: string) => update({ sort: nextSortState(sort, key) });
    const [resettingEntry, setResettingEntry] = useState<RateLimitEntry | null>(null);
    const [resetTrigger, setResetTrigger] = useState<HTMLElement | null>(null);
    // Guards handleConfirmReset against a second DELETE firing from a rapid
    // double-click before resetMutation.isPending flips true (that flip is
    // one render behind the click). A ref, not state, so the check inside
    // the handler sees the write immediately - reset via effect rather than
    // a wrapper around setResettingEntry, so nothing that touches the ref is
    // ever passed down as a prop (eslint's react-hooks/refs rule flags that
    // as a possible read-during-render, even when, as here, the only
    // caller is an onClick).
    const resetSubmitGuard = useRef(false);
    useEffect(() => {
        resetSubmitGuard.current = false;
    }, [resettingEntry]);

    const filters = {
        endpoint: endpoint || undefined,
        identifier: debouncedIdentifier || undefined,
        scope: (scope || undefined) as "ip" | "account" | "email" | undefined,
        kind: kind === "all" ? undefined : kind,
        sortBy: (sort.key === "requests" ? "count" : sort.key) as "endpoint" | "scope" | "identifier" | "count" | "resets_at",
        sortDir: sort.direction,
    };

    const [page, setPage] = usePageResetOn(`${endpoint}|${debouncedIdentifier}|${scope}|${kind}`);

    const { data, error, isFetching, isLoading, isError } = useRateLimitsQuery(page, PAGE_SIZE, filters);
    const resetMutation = useResetRateLimitMutation();
    const summaryQuery = useRateLimitsSummaryQuery();

    const entries = data?.entries ?? [];
    const totalPages = totalPagesFor(data?.total ?? 0, PAGE_SIZE);
    const hasFilters = Boolean(endpoint || identifier || scope || kind !== "all");

    const handleConfirmReset = () => {
        if (!resettingEntry || resetSubmitGuard.current || resetMutation.isPending) return;
        resetSubmitGuard.current = true;
        resetMutation.mutate(resettingEntry.key, {
            onSuccess: () => {
                toaster.create({ title: t("page.resetToast"), type: "success" });
                setResettingEntry(null);
            },
            onError: (error) => {
                toaster.create({ title: isForbiddenError(error.cause) ? t("page.resetForbidden") : error.message, type: "error" });
                setResettingEntry(null);
            },
        });
    };

    const requestReset = (entry: RateLimitEntry, trigger: HTMLElement) => {
        setResetTrigger(trigger);
        setResettingEntry(entry);
    };

    const columns = buildRateLimitsColumns({
        t,
        language,
        onResetRequest: requestReset,
        resettingKey: resetMutation.isPending ? resetMutation.variables : undefined,
    });

    return (
        <PageContainer
            title={t("page.title")}
            icon={Gauge}
            description={t("page.description")}
            headerExtra={
                <div className="flex flex-col gap-4">
                <RateLimitsStatsCard
                    summary={summaryQuery.data}
                    isLoading={summaryQuery.isLoading}
                    isError={summaryQuery.isError}
                    errorMessage={isForbiddenError(summaryQuery.error) ? t("page.readForbidden") : t("page.summaryUnavailable")}
                    activeTile={kind}
                    onFilterTotal={() => update({ endpoint: "", identifier: "", scope: "", kind: "all" })}
                    onFilterAtLimit={() => {
                        const active = kind === "at_limit";
                        update({ endpoint: "", identifier: "", scope: "", kind: active ? "all" : "at_limit" });
                    }}
                    onFilterLoginLockouts={() => {
                        const active = kind === "login_lockouts";
                        // `kind` is the dedicated login-lockout view. Do not
                        // encode it as a scope: email is a backend/API scope
                        // for individual lockout records, not a quick-filter
                        // choice on this dashboard.
                        update({
                            kind: active ? "all" : "login_lockouts",
                            endpoint: active ? "" : "login_lock",
                            identifier: "",
                            scope: "",
                        });
                    }}
                />
                <RateLimitsFilterBar
                    endpoint={endpoint} setEndpoint={setEndpoint}
                    identifier={identifier} setIdentifier={setIdentifier}
                    scope={scope} setScope={setScope}
                    isFetching={isFetching}
                    totalResults={data?.total}
                    totalCount={summaryQuery.data?.total ?? 0}
                    ipCount={summaryQuery.data?.by_scope?.ip ?? 0}
                    accountCount={summaryQuery.data?.by_scope?.account ?? 0}
                />
                </div>
            }
        >
            {data?.truncated && (
                <p className="text-sm text-fg-muted mb-2">{t("page.truncatedNote")}</p>
            )}
            {!isLoading && !isError && entries.length > 0 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} className="mb-4" />}
            <DataTable
                columns={columns}
                rows={entries}
                rowKey={(e) => e.key}
                isLoading={isLoading}
                isError={isError}
                errorMessage={isForbiddenError(error) ? t("page.readForbidden") : t("page.failedToLoad")}
                emptyMessage={t(hasFilters ? "page.noMatchingLimits" : "page.noActiveLimits")}
                emptyIcon={<ShieldAlert size={32} aria-hidden="true" />}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />
            {!isLoading && !isError && entries.length > 0 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} className="mt-4" />}

            <ConfirmDialog
                isOpen={!!resettingEntry}
                title={t("page.resetDialogTitle")}
                description={t("page.resetDialogDescription", {
                    endpoint: resettingEntry?.endpoint,
                    identifier: resettingEntry?.identifier,
                })}
                confirmLabel={t("page.reset")}
                isDestructive
                isLoading={resetMutation.isPending}
                onConfirm={handleConfirmReset}
                onCancel={() => {
                    setResettingEntry(null);
                    setResetTrigger(null);
                }}
                returnFocusElement={resetTrigger}
            />
        </PageContainer>
    );
};

export default RateLimitsPage;
