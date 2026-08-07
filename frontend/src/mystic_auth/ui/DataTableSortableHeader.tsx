import React from "react";
import { HStack } from "@chakra-ui/react";
import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";

import type { DataTableColumn } from "./DataTable";
import type { SortState } from "./hooks/useSortState";

function sortableHeaderLabel(label: string, active: boolean, direction: "asc" | "desc") {
    return (
        <HStack gap={1} cursor="pointer" userSelect="none" _hover={{ color: "brand.fg" }} role="button" tabIndex={0}>
            <span>{label}</span>
            {active ? (
                direction === "asc" ? <ArrowUp size={14} /> : <ArrowDown size={14} />
            ) : (
                <ArrowUpDown size={14} opacity={0.4} />
            )}
        </HStack>
    );
}

export function renderHeaderCell<T>(col: DataTableColumn<T>, sort: SortState | undefined) {
    if (!col.sortable) return col.header;
    const active = sort?.key === col.key;
    return sortableHeaderLabel(col.header, active, active ? sort.direction : "asc");
}

/** aria-sort belongs on the <th> itself (not the inner label span), so
 * screen readers announce a sortable table's current sort state the same
 * way sighted users see it from the arrow icon - "none" for every
 * unsorted sortable column, never omitted, so its presence alone also
 * tells assistive tech the column is sortable at all. */
export function ariaSortFor<T>(col: DataTableColumn<T>, sort: SortState | undefined): React.AriaAttributes["aria-sort"] {
    if (!col.sortable) return undefined;
    if (sort?.key !== col.key) return "none";
    return sort.direction === "asc" ? "ascending" : "descending";
}
