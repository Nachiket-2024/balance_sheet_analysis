import React, { useMemo, useState } from "react";
import { CheckCircle2, MinusCircle, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import QuickFilterSegment from "../../ui/filters/QuickFilterSegment";

import type { BulkItemResult } from "../../api/bulk_assignment_api";

interface BulkOperationResultListProps {
    results: BulkItemResult[];
}

/** Renders one bulk mutation's per-item outcome (BulkItemResult[]): which
 * selected users succeeded vs. errored, and why. Used by
 * BulkUserAccessDialog after submit, since a single success/error toast
 * can't represent "18 succeeded, 2 failed". */
const BulkOperationResultList: React.FC<BulkOperationResultListProps> = ({ results }) => {
    const { t } = useTranslation("users");
    const [query, setQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "success" | "already_held" | "error">("all");
    const filteredResults = useMemo(() => {
        const normalized = query.trim().toLowerCase();
        return results.filter((result) =>
            (statusFilter === "all" || result.status === statusFilter) &&
            (!normalized || `${result.user_email} ${result.identifier} ${result.error ?? ""}`.toLowerCase().includes(normalized))
        );
    }, [query, results, statusFilter]);
    if (results.length === 0) return null;

    const groups = [
        { key: "success", label: t("users:bulkActions.succeeded"), rows: results.filter((r) => r.status === "success"), icon: <CheckCircle2 size={15} className="text-fg-success" aria-hidden="true" /> },
        { key: "already_held", label: t("users:bulkActions.skipped"), rows: results.filter((r) => r.status === "already_held"), icon: <MinusCircle size={15} className="text-fg-muted" aria-hidden="true" /> },
        { key: "error", label: t("users:bulkActions.failed"), rows: results.filter((r) => r.status === "error"), icon: <XCircle size={15} className="text-fg-error" aria-hidden="true" /> },
    ];

    const visibleGroups = groups.map((group) => ({ ...group, rows: filteredResults.filter((r) => r.status === group.key) })).filter((group) => group.rows.length > 0);

    return (
        <div className="flex flex-col gap-2" aria-live="polite">
            <div className="flex flex-wrap items-center gap-2">
                    <input
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder={t("users:bulkActions.searchResults")}
                        aria-label={t("users:bulkActions.searchResults")}
                        className="h-8 min-w-0 flex-1 sm:w-80 sm:flex-none rounded-md border border-border-strong bg-bg-surface px-2.5 text-sm outline-none focus-visible:border-brand-solid focus-visible:ring-1 focus-visible:ring-brand-solid"
                    />
                    <QuickFilterSegment
                        value={statusFilter}
                        onChange={(value) => setStatusFilter(value as typeof statusFilter)}
                        ariaLabel={t("users:bulkActions.filterResults")}
                        options={[
                            { value: "all", label: t("users:bulkActions.allResults"), count: results.length },
                            { value: "success", label: t("users:bulkActions.succeeded"), count: results.filter((r) => r.status === "success").length },
                            { value: "already_held", label: t("users:bulkActions.skipped"), count: results.filter((r) => r.status === "already_held").length },
                            { value: "error", label: t("users:bulkActions.failed"), count: results.filter((r) => r.status === "error").length, danger: true },
                        ]}
                    />
            </div>
            <div className="flex max-h-72 flex-col gap-2 overflow-y-auto pr-1 [scrollbar-gutter:stable]">
            {visibleGroups.map((group) => (
                <section key={group.key} aria-label={group.label}>
                    <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-fg-muted">
                        {group.icon}<span>{group.label}</span><span>({group.rows.length})</span>
                    </div>
                    <div className="divide-y divide-border-card rounded-md border border-border-card bg-bg-surface">
                        {group.rows.map((r) => (
                            <div key={`${r.user_email}:${r.identifier}`} className="flex min-w-0 items-start gap-2 px-2.5 py-2 text-sm">
                                <span className="mt-0.5 shrink-0">{group.icon}</span>
                                <div className="min-w-0 flex-1">
                                    <p className="truncate font-medium text-fg-default">{r.user_email}</p>
                                    <p className="truncate text-xs text-fg-muted">{r.identifier}</p>
                                </div>
                                {r.status === "error" && <p className="min-w-0 truncate text-fg-error">{r.error}</p>}
                                {r.status === "already_held" && <p className="min-w-0 truncate text-fg-muted">{t("users:bulkActions.alreadyHeld")}</p>}
                            </div>
                        ))}
                    </div>
                </section>
            ))}
            {visibleGroups.length === 0 && <p className="py-4 text-center text-sm text-fg-muted">{t("users:accessDialog.noMatches")}</p>}
            </div>
        </div>
    );
};

export default BulkOperationResultList;
