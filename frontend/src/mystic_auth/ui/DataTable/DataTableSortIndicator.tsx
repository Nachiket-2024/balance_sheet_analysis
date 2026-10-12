import React from "react";
import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";

import type { DataTableColumn } from "./DataTable";
import type { SortState } from "../hooks/useSortState";

// Plain rendering/aria helpers only, split out of DataTableSortableHeader.tsx
// (which owns DataTableHeaderRow, a component) so that file exports only a
// component - a file mixing component and non-component exports breaks
// Fast Refresh (react-refresh/only-export-components).

function sortableHeaderLabel(label: string, active: boolean, direction: "asc" | "desc") {
    return (
        <span className="flex items-center gap-1 cursor-pointer select-none hover:text-brand-fg" role="button" tabIndex={0}>
            <span>{label}</span>
            {active ? (
                direction === "asc" ? <ArrowUp size={14} /> : <ArrowDown size={14} />
            ) : (
                <ArrowUpDown size={14} className="opacity-40" />
            )}
        </span>
    );
}

export function renderHeaderCell<T>(col: DataTableColumn<T>, sort: SortState | undefined) {
    if (!col.sortable) return col.header;
    const active = sort?.key === col.key;
    return sortableHeaderLabel(col.header, active, active ? sort.direction : "asc");
}

/** aria-sort belongs on the <th> itself (not the inner label span), so
 * screen readers announce a sortable table's current sort state the way
 * sighted users see it from the arrow icon - "none" for every unsorted
 * sortable column, never omitted, so its presence alone also tells
 * assistive tech the column is sortable at all. */
export function ariaSortFor<T>(col: DataTableColumn<T>, sort: SortState | undefined): React.AriaAttributes["aria-sort"] {
    if (!col.sortable) return undefined;
    if (sort?.key !== col.key) return "none";
    return sort.direction === "asc" ? "ascending" : "descending";
}
