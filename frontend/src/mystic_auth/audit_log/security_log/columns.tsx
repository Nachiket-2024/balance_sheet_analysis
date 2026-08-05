import { Badge, Text } from "@chakra-ui/react";

import type { DataTableColumn } from "../../ui/DataTable";
import type { SecurityAuditLogEntryRead } from "../../api/audit_api";
import { formatTimestamp } from "../auditLogListConfig";

// Every column is sortable: `key` doubles as the sort key sent to the
// backend, and every key here matches one of the backend's own allowlisted
// sortable columns for this log type (see
// audit_log/audit_log_repository.py's _SORTABLE_COLUMNS).
export const securityColumns: DataTableColumn<SecurityAuditLogEntryRead>[] = [
    { key: "created_at", header: "When", width: "190px", truncate: true, render: (e) => formatTimestamp(e.created_at), sortable: true },
    {
        key: "user_email",
        header: "User",
        width: "26%",
        truncate: true,
        // Genuinely unattributable, not a bug: the refresh token behind this
        // event (logout/logout-all) was expired or undecodable by the time
        // it was logged, so there was no payload left to recover an email
        // from (see logout_handler.py). An explicit, muted label reads as
        // "no identity available" instead of looking like a rendering bug.
        render: (e) => e.user_email ?? <Text color="fg.muted">Unknown user</Text>,
        sortable: true,
    },
    { key: "event_type", header: "Event", width: "22%", truncate: true, render: (e) => e.event_type, sortable: true },
    {
        key: "ip_address",
        header: "IP",
        width: "150px",
        truncate: true,
        render: (e) => e.ip_address ?? <Text color="fg.muted">Unknown</Text>,
        sortable: true,
    },
    {
        key: "success",
        header: "Result",
        width: "120px",
        render: (e) => <Badge colorPalette={e.success ? "green" : "red"} size="md">{e.success ? "Success" : "Failed"}</Badge>,
        sortable: true,
    },
];
