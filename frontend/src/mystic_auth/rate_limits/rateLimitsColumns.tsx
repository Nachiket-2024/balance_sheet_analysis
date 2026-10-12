import { RotateCcw } from "lucide-react";
import { cn } from "../ui/styles/classNames";
import type { TFunction } from "i18next";

import type { DataTableColumn } from "../ui/DataTable/DataTable";
import TableActionButton from "../ui/table_actions/TableActionButton";
import { formatDateTime } from "../ui/dates/dateFormatters";
import type { SupportedLanguage } from "../translations/translations";
import type { RateLimitEntry } from "../api/rate_limits_api";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import { DESTRUCTIVE_TABLE_ACTION_CLASSNAME } from "../ui/table_actions/tableActionPalettes";

interface BuildRateLimitsColumnsParams {
    t: TFunction<"rate_limits">;
    language: SupportedLanguage;
    onResetRequest: (entry: RateLimitEntry, trigger: HTMLElement) => void;
    resettingKey: string | undefined;
}

/** Same "columns as a function of page state" shape as usersColumns.tsx's
 * buildUsersColumns: the Reset action needs the page's confirm-dialog state
 * and in-flight mutation.
 *
 * Every data column is sortable, but unlike audit_log this is a client-side
 * sort over only the loaded page (see RateLimitsPage.tsx): the backend is a
 * Valkey SCAN cursor, not a SQL table, so sorting the whole live keyspace
 * would mean materializing it, which list_active_limits avoids. */
export function buildRateLimitsColumns({
    t,
    language,
    onResetRequest,
    resettingKey,
}: BuildRateLimitsColumnsParams): DataTableColumn<RateLimitEntry>[] {
    return [
        { key: "endpoint", header: t("page.endpointColumn"), width: "12rem", truncate: true, render: (e) => e.endpoint, sortable: true },
        {
            key: "scope",
            header: t("page.scopeColumn"),
            width: "10rem",
            render: (e) => <span className="text-sm">{e.scope === "ip" ? t("page.scopeIp") : e.scope === "account" ? t("page.scopeAccount") : t("page.scopeEmail")}</span>,
            sortable: true,
        },
        {
            // One column for both cases instead of two: a row's identifier
            // is either an IP or an email, never both, so a second column
            // would always be empty. The Scope badge shows which kind it is.
            key: "identifier",
            header: t("page.identifierColumn"),
            width: "16rem",
            truncate: true,
            render: (e) => e.identifier,
            sortable: true,
        },
        {
            key: "requests",
            header: t("page.requestsColumn"),
            width: "8rem",
            render: (e) => (
                <span className={cn(e.count >= e.limit && "text-fg-error font-medium")}>
                    {e.count} / {e.limit}
                </span>
            ),
            sortable: true,
        },
        {
            key: "resets_at",
            header: t("page.resetsAtColumn"),
            // See ActiveSessionsCard's matching column for why this is wider
            // than a plain ellipsis-truncated text column.
            width: "13.5rem",
            truncate: true,
            render: (e) => {
                if (e.resets_in_seconds == null) return t("page.noExpiry");
                const resetsAt = new Date(Date.now() + e.resets_in_seconds * 1000).toISOString();
                return <span className="text-sm">{formatDateTime(resetsAt, language)}</span>;
            },
            sortable: true,
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            width: "7rem",
            render: (e) => (
                <IfCan action={PERMISSIONS.RATE_LIMITS_RESET}>
                    <TableActionButton colorPalette="red" className={DESTRUCTIVE_TABLE_ACTION_CLASSNAME} onClick={(event) => onResetRequest(e, event.currentTarget)} loading={resettingKey === e.key}>
                        <RotateCcw size={14} aria-hidden="true" />
                        {t("page.reset")}
                    </TableActionButton>
                </IfCan>
            ),
        },
    ];
}
