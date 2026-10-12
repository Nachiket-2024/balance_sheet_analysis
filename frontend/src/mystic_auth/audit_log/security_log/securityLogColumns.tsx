import type { ReactNode } from "react";
import type { TFunction } from "i18next";
import { Check } from "lucide-react";

import Badge from "../../ui/badges/Badge";
import AppTooltip from "../../ui/feedback/AppTooltip";
import type { DataTableColumn } from "../../ui/DataTable/DataTable";
import type { SecurityAuditLogEntryRead } from "../../api/audit_api";
import type { SupportedLanguage } from "../../translations/translations";
import { formatTimestamp } from "../auditLogListConfig";
import { humanizeSecurityEventType } from "./securityLogEventTypes";

/** A faint dash with an explanation for genuinely unattributable users. */
function missingValue(reason: string): ReactNode {
    return (
        <AppTooltip content={reason}>
            <span className="text-fg-muted cursor-help" tabIndex={0}><span aria-hidden="true">—</span><span className="sr-only">{reason}</span></span>
        </AppTooltip>
    );
}

// Every column is sortable: `key` doubles as the sort key sent to the backend, and each one
// matches an allowlisted sortable column (see backend/mystic_auth/audit_log/audit_log_repository.py's
// _SORTABLE_COLUMNS). A function, not a plain constant, so headers/badge text can use the
// caller's own `t`.
export function getSecurityColumns(t: TFunction<"audit_log">, language: SupportedLanguage): DataTableColumn<SecurityAuditLogEntryRead>[] {
    return [
        // See ActiveSessionsCard's matching date column for why this is wider than a plain
        // ellipsis-truncated text column - fits the longest formatTimestamp output (mr's
        // longer month/day-period words) without clipping.
        { key: "created_at", header: t("security.columns.when"), width: "24%", truncate: true, render: (e) => formatTimestamp(e.created_at, language), sortable: true },
        {
            key: "user_email",
            header: t("security.columns.user"),
            width: "30%",
            truncate: true,
            // Genuinely unattributable, not a bug: the refresh token behind this event
            // (logout/logout-all) was expired or undecodable by log time, so there's no
            // payload to recover an email from (see logout_handler.py).
            render: (e) => e.user_email ?? missingValue(t("security.columns.unknownUserReason")),
            sortable: true,
        },
        { key: "event_type", header: t("security.columns.event"), width: "30%", truncate: true, render: (e) => t(`security.filterBar.eventLabels.${e.event_type}`, { defaultValue: humanizeSecurityEventType(e.event_type) }), sortable: true },
        {
            key: "success",
            header: t("security.columns.result"),
            width: "16%",
            // Same reasoning as authorizationLogColumns' allowed column: Success is the
            // common case and stays quiet, Failed is a red badge so it stands out in the
            // column at a glance.
            render: (e) =>
                e.success ? (
                    <span className="inline-flex min-h-8 items-center gap-1 text-green-800 dark:text-green-300">
                        <Check size={14} aria-hidden="true" />
                        {t("security.results.success")}
                    </span>
                ) : (
                    <span className="inline-flex min-h-8 items-center">
                        <Badge colorPalette="red" size="md">
                            {t("security.results.failed")}
                        </Badge>
                    </span>
                ),
            sortable: true,
        },
    ];
}
