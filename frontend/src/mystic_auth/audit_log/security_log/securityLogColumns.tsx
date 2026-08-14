import { Badge, Text } from "@chakra-ui/react";
import type { TFunction } from "i18next";

import type { DataTableColumn } from "../../ui/DataTable";
import type { SecurityAuditLogEntryRead } from "../../api/audit_api";
import type { SupportedLanguage } from "../../translations/translations";
import { formatTimestamp } from "../auditLogListConfig";

// Every column is sortable: `key` doubles as the sort key sent to the
// backend, and every key here matches one of the backend's own allowlisted
// sortable columns for this log type (see
// audit_log/audit_log_repository.py's _SORTABLE_COLUMNS).
// A function (not a plain constant) so headers/badge text can be translated
// via the caller's own useTranslation("audit_log") `t`.
export function getSecurityColumns(t: TFunction<"audit_log">, language: SupportedLanguage): DataTableColumn<SecurityAuditLogEntryRead>[] {
    return [
        { key: "created_at", header: t("security.columns.when"), width: "190px", truncate: true, render: (e) => formatTimestamp(e.created_at, language), sortable: true },
        {
            key: "user_email",
            header: t("security.columns.user"),
            width: "26%",
            truncate: true,
            // Genuinely unattributable, not a bug: the refresh token behind this
            // event (logout/logout-all) was expired or undecodable by the time
            // it was logged, so there was no payload left to recover an email
            // from (see logout_handler.py). An explicit, muted label reads as
            // "no identity available" instead of looking like a rendering bug.
            render: (e) => e.user_email ?? <Text color="fg.muted">{t("security.columns.unknownUser")}</Text>,
            sortable: true,
        },
        { key: "event_type", header: t("security.columns.event"), width: "22%", truncate: true, render: (e) => e.event_type, sortable: true },
        {
            key: "ip_address",
            header: t("security.columns.ip"),
            width: "150px",
            truncate: true,
            render: (e) => e.ip_address ?? <Text color="fg.muted">{t("security.columns.unknownIp")}</Text>,
            sortable: true,
        },
        {
            key: "success",
            header: t("security.columns.result"),
            width: "120px",
            render: (e) => (
                <Badge colorPalette={e.success ? "green" : "red"} size="md">
                    {e.success ? t("security.results.success") : t("security.results.failed")}
                </Badge>
            ),
            sortable: true,
        },
    ];
}
