import React, { useState } from "react";
import { ChevronRight, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "../../ui/styles/classNames";
import DataTable, { type DataTableColumn } from "../../ui/DataTable/DataTable";
import { isDestructiveAction } from "../../authorization/destructiveActions";
import { groupByResourceType } from "../../policies/logic/effectiveGrants";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "../../policies/policyCardHelpers";

export interface AccessChipItem {
    action: string;
    resource_type: string;
    /** Short label(s) naming where this grant came from - a policy name, or
     * "Direct". Omit for a list where the source is already obvious from
     * context (e.g. a raw direct-grants-only list). */
    sourceLabels?: string[];
}

interface AccessResourceCardsProps {
    items: AccessChipItem[];
    emptyText: string;
}

/**
 * AccessResourceCards
 * ----------------------------
 * Groups a flat list of (action, resource_type[, source]) grants into one
 * collapsible card per resource type, each rendered as a DataTable
 * (Action/Source columns) - the exact same collapsed-header-plus-table
 * layout PermissionsPage uses for its own resource-type groups (same
 * chevron, same plain (non-mono) header/badge font), so a permission holder sees the
 * same shape and starts from the same collapsed state whether they're
 * browsing the permission catalog or a user's effective/direct grants.
 * Groups start expanded, unlike PermissionsPage's own resource-type groups:
 * that page can be listing the entire permission catalog (many resource
 * types, worth collapsing so they don't turn into one long scroll), while
 * this renders one user's or one policy's grants - usually a handful of
 * resource types the caller opened this dialog specifically to read, so
 * starting collapsed would hide the very thing they came to see behind an
 * extra click per group.
 * Used by UserDetailsDialog, PolicyDetailsDialog, and AccountStatusCard for
 * their Effective/Direct permissions sections.
 */
const AccessResourceCards: React.FC<AccessResourceCardsProps> = ({ items, emptyText }) => {
    const { t } = useTranslation("permissions");
    // Tracks manually-collapsed groups rather than expanded ones, so the
    // default (nothing in the set) is "everything expanded" without needing
    // to know the resource types up front.
    const [collapsedTypes, setCollapsedTypes] = useState<Set<string>>(new Set());
    const toggleTypeExpanded = (type: string) => {
        setCollapsedTypes((prev) => {
            const next = new Set(prev);
            if (next.has(type)) next.delete(type);
            else next.add(type);
            return next;
        });
    };

    if (items.length === 0) {
        return <p className="text-fg-muted">{emptyText}</p>;
    }

    const groups = groupByResourceType(items);

    const columns: DataTableColumn<AccessChipItem>[] = [
        {
            key: "action",
            header: t("permissions:columns.action"),
            width: "14rem",
            truncate: true,
            render: (item) => (
                <div className="flex items-center gap-1.5">
                    <span
                        className={
                            isDestructiveAction(item.action)
                                ? "text-sm font-medium text-red-fg"
                                : "text-sm font-medium text-fg-default"
                        }
                    >
                        {formatPolicyActionLabel(item.action)}
                    </span>
                    {isDestructiveAction(item.action) && (
                        <TriangleAlert size={13} aria-hidden="true" color="var(--red-fg)" />
                    )}
                </div>
            ),
        },
        {
            key: "source",
            header: t("permissions:columns.source"),
            render: (item) =>
                item.sourceLabels && item.sourceLabels.length > 0 ? (
                    <p className="text-fg-muted">{item.sourceLabels.join(", ")}</p>
                ) : null,
        },
    ];

    return (
        <div className="flex flex-col gap-4">
            {[...groups.entries()].map(([resourceType, grants]) => {
                const isExpanded = !collapsedTypes.has(resourceType);
                return (
                    <div key={resourceType}>
                        <div
                            className={cn(
                                "flex items-center justify-between px-4 py-2.5 border border-border-default bg-bg-surface cursor-pointer rounded-t-lg text-sm leading-5",
                                isExpanded ? "rounded-b-none border-b-0" : "rounded-b-lg border-b"
                            )}
                            onClick={() => toggleTypeExpanded(resourceType)}
                            role="button"
                            tabIndex={0}
                            aria-expanded={isExpanded}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    toggleTypeExpanded(resourceType);
                                }
                            }}
                        >
                            <div className="flex items-center gap-2">
                                <ChevronRight
                                    size={16}
                                    aria-hidden="true"
                                    style={{ transform: isExpanded ? "rotate(90deg)" : undefined, transition: "transform var(--duration-hover)" }}
                                />
                                <p title={resourceType}>{formatResourceTypeLabel(resourceType)}</p>
                            </div>
                            <p className="text-fg-muted">
                                {t("permissions:page.actionCount", { count: grants.length })}
                            </p>
                        </div>
                        {isExpanded && (
                            <DataTable
                                columns={columns}
                                rows={grants}
                                rowKey={(g) => `${g.action}:${g.resource_type}`}
                                startIndex={0}
                            />
                        )}
                    </div>
                );
            })}
        </div>
    );
};

export default AccessResourceCards;
