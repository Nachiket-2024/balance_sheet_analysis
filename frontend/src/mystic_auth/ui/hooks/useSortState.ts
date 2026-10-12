import { useState } from "react";

export type SortDirection = "asc" | "desc";

export interface SortState {
    key: string;
    direction: SortDirection;
}

/**
 * Excel-style column sort: clicking a column not currently sorted sorts it
 * ascending; clicking the SAME column again flips to descending; clicking a
 * DIFFERENT column starts that one fresh at ascending, same as spreadsheet
 * software's own convention. Exported (not just used internally by
 * useSortState below) so a page backing its sort state with a store instead
 * of local useState - see rateLimitsUiStore.ts and its sibling *UiStore
 * files - can reuse the exact same toggle rule.
 */
export function nextSortState(prev: SortState, key: string): SortState {
    return prev.key === key ? { key, direction: prev.direction === "asc" ? "desc" : "asc" } : { key, direction: "asc" };
}

export function useSortState(defaultKey: string, defaultDirection: SortDirection = "desc") {
    const [sort, setSort] = useState<SortState>({ key: defaultKey, direction: defaultDirection });

    const toggleSort = (key: string) => {
        setSort((prev) => nextSortState(prev, key));
    };

    return { sort, toggleSort };
}
