import { Badge } from "@chakra-ui/react";

import type { DataTableColumn } from "../../ui/DataTable";
import type { AuthorizationAuditLogEntryRead } from "../../api/audit_api";
import { formatTimestamp } from "../auditLogListConfig";

// Every column is sortable: `key` doubles as the sort key sent to the
// backend, and every key here matches one of the backend's own allowlisted
// sortable columns for this log type (see
// authorization/repositories/audit_log_repository.py's _SORTABLE_COLUMNS).
export const authorizationColumns: DataTableColumn<AuthorizationAuditLogEntryRead>[] = [
    { key: "created_at", header: "When", width: "190px", truncate: true, render: (e) => formatTimestamp(e.created_at), sortable: true },
    { key: "user_email", header: "User", width: "26%", truncate: true, render: (e) => e.user_email, sortable: true },
    { key: "action", header: "Action", width: "22%", truncate: true, render: (e) => e.action, sortable: true },
    { key: "resource_type", header: "Resource", width: "150px", truncate: true, render: (e) => e.resource_type, sortable: true },
    {
        key: "allowed",
        header: "Result",
        width: "120px",
        render: (e) => (
            <Badge colorPalette={e.allowed ? "green" : "red"} size="md">{e.allowed ? "Allowed" : "Denied"}</Badge>
        ),
        sortable: true,
    },
];
