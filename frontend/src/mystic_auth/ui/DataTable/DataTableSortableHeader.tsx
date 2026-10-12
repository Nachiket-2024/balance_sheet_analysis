import { Checkbox } from "../shadcn/checkbox";
import { TableHead, TableRow } from "../shadcn/table";
import { cn } from "../styles/classNames";
import AppTooltip from "../feedback/AppTooltip";
import type { DataTableColumn } from "./DataTable";
import type { SortState } from "../hooks/useSortState";
import { STICKY_HEADER_CELL_CLASS } from "./DataTableStyles";
import { ariaSortFor, renderHeaderCell } from "./DataTableSortIndicator";

interface DataTableHeaderRowProps<T> {
    columns: DataTableColumn<T>[];
    sort?: SortState;
    onSortChange?: (key: string) => void;
    selectable?: boolean;
    showRowNumbers: boolean;
    isAllSelected: boolean;
    isSomeSelected: boolean;
    onToggleAll: () => void;
    selectAllLabel: string;
    /** See DataTable's onRowClick doc - adds an empty trailing header cell matching the
     * chevron-hint column DataTableRow renders on each body row. */
    hasRowClick?: boolean;
}

const ALIGN_CLASS = { start: "text-left", center: "text-center", end: "text-right" } as const;

/** The full header <tr>, split out of DataTable.tsx to keep that file's
 * render under the repo's file-length guideline - this owns only the header
 * cells, DataTableRow owns a body row, DataTable.tsx wires both up to the
 * shared column/selection state. */
export function DataTableHeaderRow<T>({
    columns,
    sort,
    onSortChange,
    selectable,
    showRowNumbers,
    isAllSelected,
    isSomeSelected,
    onToggleAll,
    selectAllLabel,
    hasRowClick,
}: DataTableHeaderRowProps<T>) {
    return (
        <TableRow className="hover:bg-transparent">
            {selectable && (
                <TableHead className={cn("w-[1%]", STICKY_HEADER_CELL_CLASS)}>
                    <Checkbox
                        checked={isAllSelected ? true : isSomeSelected ? "indeterminate" : false}
                        onCheckedChange={onToggleAll}
                        aria-label={selectAllLabel}
                        // fg-muted override: the stock unchecked border is
                        // border-input, which reads too faint against the
                        // header's bg-table-header background. fg-muted is a
                        // much stronger, text-level gray in both themes, so
                        // the select-all box stays clearly visible.
                        className="border-fg-muted"
                    />
                </TableHead>
            )}
            {showRowNumbers && (
                <TableHead className={cn("w-[1%] text-sm", STICKY_HEADER_CELL_CLASS)}>#</TableHead>
            )}
            {columns.map((col) => (
                <TableHead
                    key={col.key}
                    className={cn("text-sm overflow-hidden", col.align && ALIGN_CLASS[col.align], STICKY_HEADER_CELL_CLASS)}
                    aria-sort={ariaSortFor(col, sort)}
                    onClick={col.sortable ? () => onSortChange?.(col.key) : undefined}
                    onKeyDown={
                        col.sortable
                            ? (e) => {
                                  // SortableHeaderLabel renders role="button", but the
                                  // click handler lives here on the parent cell - a
                                  // span[role=button] doesn't fire on Enter/Space by
                                  // itself, so without this the header is focusable
                                  // but not operable via keyboard.
                                  if (e.key === "Enter" || e.key === " ") {
                                      e.preventDefault();
                                      onSortChange?.(col.key);
                                  }
                              }
                            : undefined
                    }
                >
                    {col.truncate ? (
                        <AppTooltip content={col.header}>
                            <div className="overflow-hidden text-ellipsis whitespace-nowrap">{renderHeaderCell(col, sort)}</div>
                        </AppTooltip>
                    ) : (
                        renderHeaderCell(col, sort)
                    )}
                </TableHead>
            ))}
            {hasRowClick && <TableHead className={cn("w-8", STICKY_HEADER_CELL_CLASS)} />}
        </TableRow>
    );
}
