import React from "react";
import { Box, Skeleton, Table, EmptyState, HStack } from "@chakra-ui/react";
import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";

import FormAlert from "./FormAlert";
import type { SortState } from "./hooks/useSortState";

export interface DataTableColumn<T> {
    key: string;
    header: string;
    render: (row: T) => React.ReactNode;
    /** Right-aligns numeric/action columns. */
    align?: "start" | "center" | "end";
    /** Whether clicking this column's header sorts by it (see `sort`/
     * `onSortChange` below). `key` doubles as the sort key sent to the
     * backend - every current caller's column keys already match the
     * backend's own allowlisted sortable column names 1:1. */
    sortable?: boolean;
    /** Fixed width (e.g. "160px"), applied via <colgroup> below with
     * `table-layout: fixed`. Without this, a plain HTML table sizes each
     * column from its own current cell contents, so switching filters/tabs
     * (a shorter name, an empty IP, a different badge set) reflows every
     * column width on every render - distracting movement that has nothing
     * to do with the data itself. Give a fixed width to any column whose
     * content varies a lot in length; columns left unset share the
     * remaining space evenly. */
    width?: string;
    /** Clips this column's content to one line with a trailing ellipsis
     * instead of letting it overflow into the next column - the fix for a
     * long unbroken string (an email, a UA string, an audit "action" id)
     * that has nowhere to wrap once its column has a fixed width. Set this
     * on any column whose content is free-form text of unpredictable
     * length; leave it off for columns that already manage their own
     * overflow (badges/buttons in an HStack/Wrap that's meant to wrap onto
     * a second line). When `render` returns a plain string, that string is
     * also used as the cell's `title` so the full value is still available
     * on hover. */
    truncate?: boolean;
}

/** Only a plain string/number render result can safely become a `title`
 * tooltip - anything else (badges, buttons, a name+badge Text node) is a
 * React element, not text, and can't be stringified without risk. */
function plainTextOf(node: React.ReactNode): string | undefined {
    if (typeof node === "string" || typeof node === "number") return String(node);
    return undefined;
}

// Every table here can end up wider than its container (a phone screen, or
// just a lot of columns) and falls back to Table.ScrollArea's own
// horizontal scroll - but a plain overflow:auto div gives no visual hint
// that there's more to see off to the side, so a table that's actually
// scrollable can look like it's simply cut off. The classic four-background
// "scroll shadow" trick fixes that with pure CSS: two opaque gradients
// (matching the table's own background) that cover the shadow entirely at
// each scrolled-to-the-edge extreme, and two shadow gradients underneath -
// `background-attachment: local` scrolls the opaque ones WITH the content
// (so they cover the shadow once you've scrolled past that edge) while
// `scroll` pins the shadow gradients to the viewport (so they only show
// while there's still more content in that direction). Colors reference
// Chakra's own CSS custom properties, so this needs no separate dark-mode
// override - the variable's value already flips with color mode.
const SCROLL_SHADOW_CSS = {
    background: `
        linear-gradient(to right, var(--chakra-colors-bg-surface) 30%, transparent),
        linear-gradient(to left, var(--chakra-colors-bg-surface) 30%, transparent) 100% 0,
        linear-gradient(to right, var(--chakra-colors-blackAlpha-400), transparent),
        linear-gradient(to left, var(--chakra-colors-blackAlpha-400), transparent) 100% 0
    `,
    backgroundRepeat: "no-repeat" as const,
    backgroundColor: "bg.surface",
    backgroundSize: "24px 100%, 24px 100%, 10px 100%, 10px 100%",
    backgroundPosition: "0 0, 100% 0, 0 0, 100% 0",
    backgroundAttachment: "local, local, scroll, scroll" as const,
};

interface DataTableProps<T> {
    columns: DataTableColumn<T>[];
    rows: T[] | undefined;
    rowKey: (row: T) => string | number;
    isLoading?: boolean;
    isError?: boolean;
    errorMessage?: string;
    emptyMessage?: string;
    /** Rows of skeleton placeholders shown while isLoading, mirrors the
     * shape of the real table rather than swapping to a spinner, so the
     * layout doesn't jump once data arrives. */
    skeletonRowCount?: number;
    /** Current sort column/direction, if any column is `sortable`. Omit
     * entirely for a table with no sortable columns. */
    sort?: SortState;
    /** Called with a column's `key` when its (sortable) header is clicked.
     * Required if any column sets `sortable`. */
    onSortChange?: (key: string) => void;
    /** When set, prepends a numbered "#" column so rows are easy to track
     * by position - `startIndex + 1` for the first rendered row. Pass the
     * page offset (e.g. `(page - 1) * PAGE_SIZE`) for a server-paginated
     * table so numbers reflect the row's real position across the whole
     * result set, not just its position on the current page; pass `0` for
     * an unpaginated/client-filtered table. Omit entirely for a table where
     * row position isn't meaningful (e.g. one already keyed by a visible
     * id/name column). */
    startIndex?: number;
}

function SortableHeaderLabel({
    label,
    active,
    direction,
}: {
    label: string;
    active: boolean;
    direction: "asc" | "desc";
}) {
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

function renderHeaderCell<T>(col: DataTableColumn<T>, sort: SortState | undefined) {
    if (!col.sortable) return col.header;
    return (
        <SortableHeaderLabel
            label={col.header}
            active={sort?.key === col.key}
            direction={sort?.key === col.key ? sort.direction : "asc"}
        />
    );
}

/** aria-sort belongs on the <th> itself (not the inner label span), so
 * screen readers announce a sortable table's current sort state the same
 * way sighted users see it from the arrow icon - "none" for every
 * unsorted sortable column, never omitted, so its presence alone also
 * tells assistive tech the column is sortable at all. */
function ariaSortFor<T>(col: DataTableColumn<T>, sort: SortState | undefined): React.AriaAttributes["aria-sort"] {
    if (!col.sortable) return undefined;
    if (sort?.key !== col.key) return "none";
    return sort.direction === "asc" ? "ascending" : "descending";
}

/**
 * Generic table with a shared loading/error/empty treatment, so every admin
 * list page (Users, Policies, Audit Log) doesn't reimplement the same three
 * conditional branches around a bare Chakra Table.
 */
function DataTable<T>({
    columns,
    rows,
    rowKey,
    isLoading,
    isError,
    errorMessage = "Failed to load data",
    emptyMessage = "No data available",
    skeletonRowCount = 5,
    sort,
    onSortChange,
    startIndex,
}: DataTableProps<T>) {
    const showRowNumbers = startIndex !== undefined;

    const colgroup = (
        <colgroup>
            {showRowNumbers && <col style={{ width: "48px" }} />}
            {columns.map((col) => (
                <col key={col.key} style={col.width ? { width: col.width } : undefined} />
            ))}
        </colgroup>
    );

    if (isLoading) {
        return (
            // fontSize here (not size="md"/"lg", which only changes cell
            // padding, not text) cascades to every cell/header that doesn't
            // set its own - one bump for every table's plain text at once,
            // to match the row-action buttons' and status badges' own size.
            <Table.ScrollArea borderWidth="1px" borderColor="border.default" rounded="lg" css={SCROLL_SHADOW_CSS}>
                <Table.Root size="sm" css={{ tableLayout: "fixed", width: "100%", fontSize: "15px" }}>
                    {colgroup}
                    <Table.Header>
                        <Table.Row>
                            {showRowNumbers && <Table.ColumnHeader w="1%" fontSize="16px">#</Table.ColumnHeader>}
                            {columns.map((col) => (
                                <Table.ColumnHeader
                                    key={col.key}
                                    textAlign={col.align}
                                    overflow="hidden"
                                    fontSize="16px"
                                    aria-sort={ariaSortFor(col, sort)}
                                >
                                    {renderHeaderCell(col, sort)}
                                </Table.ColumnHeader>
                            ))}
                        </Table.Row>
                    </Table.Header>
                    <Table.Body>
                        {Array.from({ length: skeletonRowCount }).map((_, rowIndex) => (
                            <Table.Row key={rowIndex}>
                                {showRowNumbers && (
                                    <Table.Cell>
                                        <Skeleton height="16px" />
                                    </Table.Cell>
                                )}
                                {columns.map((col) => (
                                    <Table.Cell key={col.key}>
                                        <Skeleton height="16px" />
                                    </Table.Cell>
                                ))}
                            </Table.Row>
                        ))}
                    </Table.Body>
                </Table.Root>
            </Table.ScrollArea>
        );
    }

    if (isError) {
        return <FormAlert status="error">{errorMessage}</FormAlert>;
    }

    if (!rows || rows.length === 0) {
        return (
            <EmptyState.Root size="sm">
                <EmptyState.Content>
                    <EmptyState.Title>{emptyMessage}</EmptyState.Title>
                </EmptyState.Content>
            </EmptyState.Root>
        );
    }

    return (
        <Table.ScrollArea borderWidth="1px" borderColor="border.default" rounded="lg">
            <Table.Root size="sm" striped css={{ tableLayout: "fixed", width: "100%", fontSize: "15px" }}>
                {colgroup}
                <Table.Header>
                    <Table.Row>
                        {showRowNumbers && <Table.ColumnHeader w="1%" fontSize="16px">#</Table.ColumnHeader>}
                        {columns.map((col) => (
                            <Table.ColumnHeader
                                key={col.key}
                                textAlign={col.align}
                                overflow="hidden"
                                fontSize="16px"
                                aria-sort={ariaSortFor(col, sort)}
                                onClick={col.sortable ? () => onSortChange?.(col.key) : undefined}
                                onKeyDown={
                                    col.sortable
                                        ? (e) => {
                                              // SortableHeaderLabel renders role="button", but the
                                              // click handler lives here on the parent cell - a
                                              // span[role=button] (unlike a real <button>) doesn't
                                              // fire on Enter/Space by itself, so without this the
                                              // header is focusable but not actually operable via
                                              // keyboard.
                                              if (e.key === "Enter" || e.key === " ") {
                                                  e.preventDefault();
                                                  onSortChange?.(col.key);
                                              }
                                          }
                                        : undefined
                                }
                            >
                                {col.truncate ? (
                                    <Box
                                        overflow="hidden"
                                        textOverflow="ellipsis"
                                        whiteSpace="nowrap"
                                        title={col.header}
                                    >
                                        {renderHeaderCell(col, sort)}
                                    </Box>
                                ) : (
                                    renderHeaderCell(col, sort)
                                )}
                            </Table.ColumnHeader>
                        ))}
                    </Table.Row>
                </Table.Header>
                <Table.Body>
                    {rows.map((row, rowIndex) => (
                        <Table.Row key={rowKey(row)}>
                            {showRowNumbers && (
                                <Table.Cell color="fg.muted">{(startIndex as number) + rowIndex + 1}</Table.Cell>
                            )}
                            {columns.map((col) => {
                                const content = col.render(row);
                                return (
                                    <Table.Cell key={col.key} textAlign={col.align} overflow="hidden">
                                        {col.truncate ? (
                                            <Box
                                                overflow="hidden"
                                                textOverflow="ellipsis"
                                                whiteSpace="nowrap"
                                                title={plainTextOf(content)}
                                            >
                                                {content}
                                            </Box>
                                        ) : (
                                            content
                                        )}
                                    </Table.Cell>
                                );
                            })}
                        </Table.Row>
                    ))}
                </Table.Body>
            </Table.Root>
        </Table.ScrollArea>
    );
}

export default DataTable;
