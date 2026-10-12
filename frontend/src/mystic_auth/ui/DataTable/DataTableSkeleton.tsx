import React from "react";

import { Skeleton } from "../shadcn/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../shadcn/table";
import { cn } from "../styles/classNames";
import { ariaSortFor, renderHeaderCell } from "./DataTableSortIndicator";
import { SCROLL_AREA_CLASS } from "./DataTableStyles";
import type { DataTableColumn } from "./DataTable";
import type { SortState } from "../hooks/useSortState";

interface DataTableSkeletonProps<T> {
    columns: DataTableColumn<T>[];
    colgroup: React.ReactNode;
    showRowNumbers: boolean;
    skeletonRowCount: number;
    sort: SortState | undefined;
}

const ALIGN_CLASS = { start: "text-left", center: "text-center", end: "text-right" } as const;

/** DataTable's isLoading state: same column headers as the real table, with
 * skeleton placeholder cells instead of rows, so the layout doesn't jump
 * once data arrives. */
function DataTableSkeleton<T>({ columns, colgroup, showRowNumbers, skeletonRowCount, sort }: DataTableSkeletonProps<T>) {
    return (
        // text-sm here (not a size prop, which only changes cell padding,
        // not text) cascades to every cell/header that doesn't set its own,
        // matching the row-action buttons' and badges' size.
        <div className={cn("border border-border-default rounded-lg overflow-x-auto", SCROLL_AREA_CLASS)}>
            <Table className="table-fixed w-full text-sm">
                {colgroup}
                <TableHeader>
                    <TableRow className="hover:bg-transparent">
                        {showRowNumbers && <TableHead className="w-[1%] text-sm">#</TableHead>}
                        {columns.map((col) => (
                            <TableHead
                                key={col.key}
                                className={cn("overflow-hidden text-sm", col.align && ALIGN_CLASS[col.align])}
                                aria-sort={ariaSortFor(col, sort)}
                            >
                                {renderHeaderCell(col, sort)}
                            </TableHead>
                        ))}
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {Array.from({ length: skeletonRowCount }).map((_, rowIndex) => (
                        <TableRow key={rowIndex}>
                            {showRowNumbers && (
                                <TableCell>
                                    <Skeleton className="h-4" />
                                </TableCell>
                            )}
                            {columns.map((col) => (
                                <TableCell key={col.key}>
                                    <Skeleton className="h-4" />
                                </TableCell>
                            ))}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
}

export default DataTableSkeleton;
