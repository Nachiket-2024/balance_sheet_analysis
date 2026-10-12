/* eslint-disable react-refresh/only-export-components -- the page imports the feature column factory from this module. */
import { Eye, TriangleAlert } from "lucide-react";

import DataTable, { type DataTableColumn } from "../ui/DataTable/DataTable";
import TableActionIconButton from "../ui/table_actions/TableActionIconButton";
import { isDestructiveAction } from "../authorization/destructiveActions";
import type {
  PermissionCatalogEntry,
  PermissionUsageEntry,
} from "../api/permissions_api";
import { formatPolicyActionLabel } from "../policies/policyCardHelpers";

type Translate = (key: string, options?: Record<string, unknown>) => string;

export function createPermissionTableColumns(
  t: Translate,
  usageFor: (action: string) => PermissionUsageEntry | undefined,
  isUsageError: boolean,
  onView: (entry: PermissionCatalogEntry) => void,
): DataTableColumn<PermissionCatalogEntry>[] {
  return [
    {
      key: "action",
      header: t("permissions:columns.action"),
      width: "17rem",
      truncate: true,
      render: (entry) => (
        <div className="flex items-center gap-1.5">
          <span
            className={
              isDestructiveAction(entry.action)
                ? "text-sm font-medium text-red-fg"
                : "text-sm font-medium text-fg-default"
            }
          >
            {formatPolicyActionLabel(entry.action)}
          </span>
          {isDestructiveAction(entry.action) && (
            <TriangleAlert size={13} aria-hidden="true" color="var(--red-fg)" />
          )}
        </div>
      ),
    },
    {
      key: "description",
      header: t("permissions:columns.description"),
      render: (entry) => (
        <span className="text-fg-muted line-clamp-2" title={entry.description}>
          {entry.description}
        </span>
      ),
    },
    {
      key: "held_by",
      header: t("permissions:columns.heldBy"),
      width: "11rem",
      render: (entry) => {
        const usage = usageFor(entry.action);
        if (isUsageError) return <span className="text-fg-subtle">–</span>;
        if (!usage) return <span className="text-fg-subtle">…</span>;
        return usage.total_user_count === 0 ? (
          <span className="text-fg-subtle text-sm">
            {t("permissions:page.heldByNone")}
          </span>
        ) : (
          <div className="flex min-w-0 flex-col items-start gap-0.5">
            <span className="text-sm font-medium text-fg-default">
              {t("permissions:page.heldByCount", {
                count: usage.total_user_count,
              })}
            </span>
            <span className="text-xs leading-4 text-fg-muted">
              {t("permissions:page.heldBySources", {
                direct: usage.direct_grant_count,
                policies: usage.policies.length,
              })}
            </span>
          </div>
        );
      },
    },
    {
      key: "row_actions",
      header: "",
      align: "end",
      width: "3.5rem",
      render: (entry) => (
        <TableActionIconButton
          colorPalette="neutral"
          label={t("permissions:columns.view")}
          onClick={() => onView(entry)}
        >
          <Eye size={18} aria-hidden="true" />
        </TableActionIconButton>
      ),
    },
  ];
}

export { DataTable };
