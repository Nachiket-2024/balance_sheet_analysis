import React, { useState } from "react";

/**
 * Resets `page` back to 1 whenever `resetKey` changes (a search term, a
 * filter, or a sort column/direction change, any of which make whatever page
 * you were on potentially meaningless - e.g. page 3 of an unfiltered list may
 * not exist at all once filtered). Adjusted during render, not an effect, to
 * avoid an extra render: the same "state derived from a changed value"
 * pattern PolicyFormDialog/UserPoliciesDialog use for their own
 * reset-on-open. Returns the page-reset state pair to use in place of a bare
 * useState(1).
 *
 * Callers build `resetKey` themselves (typically a `|`-joined string of every
 * search/filter/sort value that affects the result set), since which values
 * actually invalidate the current page differs per page.
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
