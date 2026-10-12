import React, { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "../../ui/buttons/Button";
import LoadingState from "../../ui/feedback/LoadingState";
import Pagination from "../../ui/navigation/Pagination";
import ConfirmDialog from "../../ui/feedback/ConfirmDialog";
import { formatDateTime } from "../../ui/dates/dateFormatters";
import type { SupportedLanguage } from "../../translations/translations";
import { usePolicyHistoryQuery } from "../queries/policyQueries";
import { useRollbackPolicyMutation } from "../queries/policyMutations";
import type { PolicyHistoryEntryRead } from "../../api/policies_api";

const HISTORY_PAGE_SIZE = 5;

/** One line describing a history entry: "Updated actions, description",
 * "Created this policy", etc. Mirrors design/policies.html's Recent
 * changes rows, but built from the real changed_fields/change_type
 * instead of hardcoded copy. */
function describeChange(entry: PolicyHistoryEntryRead, t: ReturnType<typeof useTranslation>["t"]): string {
    switch (entry.change_type) {
        case "created":
            return t("policies:detailsDialog.changeCreated");
        case "deleted":
            return t("policies:detailsDialog.changeDeleted");
        case "rolled_back":
            return t("policies:detailsDialog.changeRolledBack");
        default:
            return entry.changed_fields?.length
                ? t("policies:detailsDialog.changeUpdatedFields", { fields: entry.changed_fields.join(", ") })
                : t("policies:detailsDialog.changeUpdatedGeneric");
    }
}

interface PolicyHistorySectionProps {
    policyName: string;
    isOpen: boolean;
    canEdit: boolean;
    isProtected: boolean;
    language: SupportedLanguage;
    /** Reset when the dialog re-opens on a different policy/entry point -
     * see PolicyDetailsDialog's resetKey. Bumping this remounts the section,
     * which clears its page/rollback state without lifting it up. */
    resetKey: string;
}

/** "History and conditions" section's recent-changes half of
 * PolicyDetailsDialog: the paginated change list, each entry's rollback
 * button, and the rollback confirmation dialog. Owns its own page/rollback
 * state so the parent dialog doesn't have to - split out of one 407-line
 * file, see AGENTS.md's ~350-line target. */
const PolicyHistorySection: React.FC<PolicyHistorySectionProps> = ({
    policyName,
    isOpen,
    canEdit,
    isProtected,
    language,
    resetKey,
}) => {
    const { t } = useTranslation(["policies", "ui_text"]);
    const [historyPage, setHistoryPage] = useState(1);
    const [rollbackEntry, setRollbackEntry] = useState<PolicyHistoryEntryRead | null>(null);
    const [previousResetKey, setPreviousResetKey] = useState(resetKey);
    if (resetKey !== previousResetKey) {
        setPreviousResetKey(resetKey);
        setHistoryPage(1);
        setRollbackEntry(null);
    }

    // Enabled only while the dialog is actually open - a closed dialog
    // shouldn't keep refetching a policy's history in the background.
    const { data: history, isLoading: isHistoryLoading, isError: isHistoryError, refetch: refetchHistory } =
        usePolicyHistoryQuery(policyName, historyPage, HISTORY_PAGE_SIZE, isOpen);
    const rollbackMutation = useRollbackPolicyMutation();

    const historyEntries = history?.entries ?? [];
    const historyTotalPages = Math.max(1, Math.ceil((history?.total ?? 0) / HISTORY_PAGE_SIZE));

    return (
        <>
            {isHistoryLoading ? (
                <LoadingState message={t("ui_text:loading")} />
            ) : isHistoryError ? (
                <div className="flex flex-col gap-2">
                    <span className="text-fg-error">{t("policies:detailsDialog.historyLoadError")}</span>
                    <Button variant="secondary" size="sm" onClick={() => void refetchHistory()}>
                        {t("ui_text:retry")}
                    </Button>
                </div>
            ) : !historyEntries.length ? (
                <span className="text-fg-muted">{t("policies:detailsDialog.noRecentChanges")}</span>
            ) : (
                <div className="flex flex-col gap-2">
                    {historyEntries.map((entry) => (
                        <div key={entry.id} className="flex flex-col gap-0.5 text-sm">
                            <div className="flex items-start justify-between gap-2">
                                <span>{describeChange(entry, t)}</span>
                                {canEdit && (
                                    <Button
                                        size="sm"
                                        variant="secondary"
                                        disabled={isProtected || rollbackMutation.isPending}
                                        title={isProtected ? t("policies:detailsDialog.rollbackProtected") : undefined}
                                        onClick={() => {
                                            rollbackMutation.reset();
                                            setRollbackEntry(entry);
                                        }}
                                    >
                                        {t("policies:detailsDialog.rollback")}
                                    </Button>
                                )}
                            </div>
                            <span className="text-xs text-fg-muted">
                                {entry.changed_by || t("policies:detailsDialog.changedBySystem")} · {formatDateTime(entry.created_at, language)}
                            </span>
                        </div>
                    ))}
                    <Pagination page={historyPage} totalPages={historyTotalPages} onPageChange={setHistoryPage} />
                </div>
            )}
            <ConfirmDialog
                isOpen={!!rollbackEntry}
                title={t("policies:detailsDialog.rollbackTitle")}
                description={rollbackMutation.error?.message ?? t("policies:detailsDialog.rollbackDescription", { policyName })}
                confirmLabel={t("policies:detailsDialog.rollback")}
                isDestructive={false}
                isLoading={rollbackMutation.isPending}
                onCancel={() => setRollbackEntry(null)}
                onConfirm={() => {
                    if (!rollbackEntry) return;
                    rollbackMutation.mutate(
                        { policyName, historyId: rollbackEntry.id },
                        { onSuccess: () => setRollbackEntry(null) },
                    );
                }}
            />
        </>
    );
};

export default PolicyHistorySection;
