import React from "react";
import { ChevronRight } from "lucide-react";

import { cn } from "../ui/styles/classNames";
import DataTable, { type DataTableColumn } from "../ui/DataTable/DataTable";
import { isDestructiveAction } from "../authorization/destructiveActions";
import type {
  PermissionCatalogEntry,
  PermissionUsageEntry,
} from "../api/permissions_api";
import {
  formatResourceTypeLabel,
  RESOURCE_TYPE_ICONS,
  resourceTypeIconTone,
} from "../policies/policyCardHelpers";

type Translate = (key: string, options?: Record<string, unknown>) => string;

interface PermissionGroupListProps {
  groups: Map<string, PermissionCatalogEntry[]>;
  expandedTypes: Set<string>;
  hasSearchOrFilters: boolean;
  isUsageError: boolean;
  usageFor: (action: string) => PermissionUsageEntry | undefined;
  columns: DataTableColumn<PermissionCatalogEntry>[];
  t: Translate;
  onToggle: (type: string) => void;
}

const PermissionGroupList: React.FC<PermissionGroupListProps> = ({
  groups,
  expandedTypes,
  hasSearchOrFilters,
  isUsageError,
  usageFor,
  columns,
  t,
  onToggle,
}) => (
  <div className="flex flex-col gap-4">
    {[...groups.entries()].map(([type, entries]) => {
      const isExpanded = hasSearchOrFilters || expandedTypes.has(type);
      const panelId = `permission-group-${type.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
      const destructiveCount = entries.filter((entry) =>
        isDestructiveAction(entry.action),
      ).length;
      const inPolicyCount = entries.filter(
        (entry) => !!usageFor(entry.action)?.policies.length,
      ).length;
      const ResourceIcon =
        RESOURCE_TYPE_ICONS[type] ?? RESOURCE_TYPE_ICONS["*"];
      return (
        <div key={type}>
          <button
            type="button"
            aria-expanded={isExpanded}
            aria-controls={panelId}
            onClick={() => onToggle(type)}
            className={cn(
              "flex w-full items-center justify-between rounded-2xl border border-border-card bg-bg-surface/70 p-3 text-left shadow-card transition-[background-color,border-color] duration-[var(--duration-fast)] ease-[var(--easing-hover)] hover:border-[var(--brand-500)] hover:bg-brand-tile-subtle focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-2 sm:p-4",
              isExpanded
                ? "rounded-b-none border-b-0"
                : "rounded-b-lg border-b",
            )}
          >
            <span className="flex min-w-0 flex-1 items-center gap-2 text-sm leading-5">
              <ChevronRight
                size={16}
                aria-hidden="true"
                style={{
                  transform: isExpanded ? "rotate(90deg)" : undefined,
                  transition: "transform var(--duration-hover)",
                }}
              />
              <ResourceIcon
                size={18}
                className={cn("shrink-0", resourceTypeIconTone(type))}
                aria-hidden="true"
              />
              <span title={type}>
                {formatResourceTypeLabel(type)}
              </span>
              {destructiveCount > 0 && (
                <span className="text-fg-error font-semibold">
                  {t("permissions:page.groupDestructiveCount", {
                    count: destructiveCount,
                  })}
                </span>
              )}
              {!isUsageError && (
                <span className="text-fg-muted">
                  {t("permissions:page.groupInPolicyCount", {
                    count: inPolicyCount,
                  })}
                </span>
              )}
              <span className="text-fg-muted">
                {t("permissions:page.actionCount", { count: entries.length })}
              </span>
            </span>
          </button>
          <div
            id={panelId}
            role="region"
            aria-label={formatResourceTypeLabel(type)}
            hidden={!isExpanded}
          >
            {isExpanded && (
              <DataTable
                columns={columns}
                rows={entries}
                rowKey={(entry) => `${entry.action}:${entry.resource_type}`}
                startIndex={0}
              />
            )}
          </div>
        </div>
      );
    })}
  </div>
);

export default PermissionGroupList;
