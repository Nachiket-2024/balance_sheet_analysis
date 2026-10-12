import type { TFunction } from "i18next";
import { Check } from "lucide-react";

import Badge from "../../ui/badges/Badge";
import type { DataTableColumn } from "../../ui/DataTable/DataTable";
import type { AuthorizationAuditLogEntryRead } from "../../api/audit_api";
import type { SupportedLanguage } from "../../translations/translations";
import { formatTimestamp } from "../auditLogListConfig";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "../../policies/policyCardHelpers";

// Every column is sortable: `key` doubles as the sort key sent to the backend, and each one
// matches an allowlisted sortable column (see
// authorization/repositories/authorization_audit_log_repository.py's _SORTABLE_COLUMNS).
// A function, not a plain constant, so headers/badge text can use the caller's own `t`.
export function getAuthorizationColumns(t: TFunction<"audit_log">, language: SupportedLanguage): DataTableColumn<AuthorizationAuditLogEntryRead>[] {
    return [
        // See ActiveSessionsCard's matching date column for why this is wider than a plain
        // ellipsis-truncated text column - fits the longest formatTimestamp output (mr's
        // longer month/day-period words) without clipping.
        { key: "created_at", header: t("authorization.columns.when"), width: "20%", truncate: true, render: (e) => formatTimestamp(e.created_at, language), sortable: true },
        { key: "user_email", header: t("authorization.columns.user"), width: "24%", truncate: true, render: (e) => e.user_email, sortable: true },
        {
            key: "action",
            header: t("authorization.columns.action"),
            width: "22%",
            truncate: true,
            render: (e) => formatPolicyActionLabel(e.action),
            sortable: true,
        },
        {
            key: "resource_type",
            header: t("authorization.columns.resource"),
            width: "22%",
            truncate: true,
            // resource_identifier (which record within resource_type, e.g. a specific
            // user id) sits below the type in the same cell rather than its own column: it's
            // only ever meaningful alongside resource_type, never sorted/filtered on its own.
            render: (e) => (
                <div className="flex flex-col leading-tight">
                    <span>{formatResourceTypeLabel(e.resource_type)}</span>
                    {e.resource_identifier && (
                        <span className="text-xs text-fg-muted truncate">{e.resource_identifier}</span>
                    )}
                </div>
            ),
            sortable: true,
        },
        {
            key: "allowed",
            header: t("authorization.columns.result"),
            width: "12%",
            // Allowed is the overwhelming common case in a healthy log, so it stays quiet
            // (a check + plain text) rather than a colored badge - a Denied badge is what
            // should catch the eye scanning down the column, not "yet another green pill".
            render: (e) =>
                e.allowed ? (
                    <span className="inline-flex min-h-8 items-center gap-1 text-green-800 dark:text-green-300">
                        <Check size={14} aria-hidden="true" />
                        {t("authorization.results.allowed")}
                    </span>
                ) : (
                    <span className="inline-flex min-h-8 items-center">
                        <Badge colorPalette="red" size="md">
                            {t("authorization.results.denied")}
                        </Badge>
                    </span>
                ),
            sortable: true,
        },
    ];
}
