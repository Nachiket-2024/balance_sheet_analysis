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
 * software's own convention.
 */
export function useSortState(defaultKey: string, defaultDirection: SortDirection = "desc") {
    const [sort, setSort] = useState<SortState>({ key: defaultKey, direction: defaultDirection });

    const toggleSort = (key: string) => {
        setSort((prev) => (prev.key === key ? { key, direction: prev.direction === "asc" ? "desc" : "asc" } : { key, direction: "asc" }));
    };

    return { sort, toggleSort };
}
