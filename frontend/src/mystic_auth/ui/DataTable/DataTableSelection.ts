/** Same shape as React's `Dispatch<SetStateAction<T>>`: accepts a plain
 * value or an updater keyed off the current state at apply time, not the
 * render-time `selectedKeys` closure. See toggleRow/toggleAll below. */
export type SelectionChangeHandler = (
    update: Set<string | number> | ((prev: ReadonlySet<string | number>) => Set<string | number>)
) => void;

/**
 * Row-selection bookkeeping shared by DataTable's checkbox column and
 * "N selected / Clear selection" bar. This hook owns no state of its own;
 * `selectedKeys`/`onSelectionChange` come from the caller, so selection
 * survives a page/filter change exactly as the caller decides.
 */
export function useDataTableSelection<T>({
    rows,
    rowKey,
    selectedKeys,
    onSelectionChange,
    disabledKeys,
}: {
    rows: T[] | undefined;
    rowKey: (row: T) => string | number;
    selectedKeys: ReadonlySet<string | number> | undefined;
    onSelectionChange: SelectionChangeHandler | undefined;
    /** Row keys excluded from "select all"/toggle-all entirely (e.g. a row
     * that can never be bulk-acted on, like the caller's own current
     * session in ActiveSessionsCard). Without this, toggleAll's own
     * all-selected check can never be satisfied once such a row exists
     * (its key can never enter `selectedKeys`), so a second click on the
     * header checkbox keeps selecting instead of toggling back off. */
    disabledKeys?: ReadonlySet<string | number>;
}) {
    // "Select all" only covers rows actually rendered now (this page,
    // this filter) and not excluded via disabledKeys.
    const allKeysOnScreen = (rows?.map(rowKey) ?? []).filter((k) => !disabledKeys?.has(k));
    const selectedOnScreenCount = allKeysOnScreen.filter((k) => selectedKeys?.has(k)).length;
    const isAllSelected = allKeysOnScreen.length > 0 && selectedOnScreenCount === allKeysOnScreen.length;
    const isSomeSelected = selectedOnScreenCount > 0 && !isAllSelected;

    // toggleRow/toggleAll/clearSelection all use the functional form of
    // onSelectionChange, computing `next` from `prev` at commit time, not
    // the render-time `selectedKeys` prop. Several rapid selection clicks
    // could otherwise apply out of order, with a stale handler overwriting a
    // newer one and resurrecting a cleared selection.
    const toggleRow = (key: string | number) => {
        onSelectionChange?.((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const toggleAll = () => {
        onSelectionChange?.((prev) => {
            const next = new Set(prev);
            // Recomputed off `prev`, not the display-only `isAllSelected`,
            // for the same staleness reason as toggleRow.
            const allSelected = allKeysOnScreen.length > 0 && allKeysOnScreen.every((k) => prev.has(k));
            if (allSelected) allKeysOnScreen.forEach((k) => next.delete(k));
            else allKeysOnScreen.forEach((k) => next.add(k));
            return next;
        });
    };

    const clearSelection = () => {
        onSelectionChange?.((prev) => {
            const next = new Set(prev);
            allKeysOnScreen.forEach((k) => next.delete(k));
            return next;
        });
    };

    return {
        allKeysOnScreen,
        selectedOnScreenCount,
        isAllSelected,
        isSomeSelected,
        toggleRow,
        toggleAll,
        clearSelection,
    };
}
