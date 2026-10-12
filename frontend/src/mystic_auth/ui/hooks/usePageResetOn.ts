import React, { useState } from "react";

/**
 * Resets `page` back to 1 whenever `resetKey` changes (a search term, filter,
 * or sort change, any of which can make the current page meaningless).
 * Adjusted during render, not an effect, to avoid an extra render - same
 * pattern as PolicyFormDialog/UserPoliciesDialog's reset-on-open. Returns
 * the page-reset state pair to use in place of a bare useState(1).
 *
 * Callers build `resetKey` themselves (typically a `|`-joined string of
 * every search/filter/sort value that affects the result set).
 */
export function usePageResetOn(resetKey: string): [number, React.Dispatch<React.SetStateAction<number>>] {
    const [page, setPage] = useState(1);
    const [prevResetKey, setPrevResetKey] = useState(resetKey);
    if (resetKey !== prevResetKey) {
        setPrevResetKey(resetKey);
        setPage(1);
    }
    return [page, setPage];
}
