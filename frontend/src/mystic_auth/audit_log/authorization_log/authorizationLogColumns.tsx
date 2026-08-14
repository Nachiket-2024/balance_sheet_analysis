import { Badge } from "@chakra-ui/react";
import type { TFunction } from "i18next";

import type { DataTableColumn } from "../../ui/DataTable";
import type { AuthorizationAuditLogEntryRead } from "../../api/audit_api";
import type { SupportedLanguage } from "../../translations/translations";
import { formatTimestamp } from "../auditLogListConfig";

// Every column is sortable: `key` doubles as the sort key sent to the
// backend, and every key here matches one of the backend's own allowlisted
// sortable columns for this log type (see
// authorization/repositories/audit_log_repository.py's _SORTABLE_COLUMNS).
// A function (not a plain constant) so headers/badge text can be translated
// via the caller's own useTranslation("audit_log") `t`.
export function getAuthorizationColumns(t: TFunction<"audit_log">, language: SupportedLanguage): DataTableColumn<AuthorizationAuditLogEntryRead>[] {
    return [
        { key: "created_at", header: t("authorization.columns.when"), width: "190px", truncate: true, render: (e) => formatTimestamp(e.created_at, language), sortable: true },
        { key: "user_email", header: t("authorization.columns.user"), width: "26%", truncate: true, render: (e) => e.user_email, sortable: true },
        { key: "action", header: t("authorization.columns.action"), width: "22%", truncate: true, render: (e) => e.action, sortable: true },
        { key: "resource_type", header: t("authorization.columns.resource"), width: "150px", truncate: true, render: (e) => e.resource_type, sortable: true },
        {
            key: "allowed",
            header: t("authorization.columns.result"),
            width: "120px",
            render: (e) => (
                <Badge colorPalette={e.allowed ? "green" : "red"} size="md">
                    {e.allowed ? t("authorization.results.allowed") : t("authorization.results.denied")}
                </Badge>
            ),
            sortable: true,
        },
    ];
}
