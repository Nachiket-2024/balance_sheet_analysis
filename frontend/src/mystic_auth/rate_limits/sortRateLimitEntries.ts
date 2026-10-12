import type { SortState } from "../ui/hooks/useSortState";
import type { RateLimitEntry } from "../api/rate_limits_api";

// Column key -> value extractor. "requests" sorts by count, not the
// count/limit ratio (limit is the same constant for every row today, so
// they'd order the same anyway). "resets_at" sorts by resets_in_seconds,
// treating null (no expiry) as +Infinity, so it sorts last ascending and
// first descending, like any other largest value would.
const SORT_VALUE: Record<string, (e: RateLimitEntry) => string | number> = {
    endpoint: (e) => e.endpoint,
    scope: (e) => e.scope,
    identifier: (e) => e.identifier,
    requests: (e) => e.count,
    resets_at: (e) => e.resets_in_seconds ?? Number.POSITIVE_INFINITY,
};

/** Client-side sort over whatever page(s) have loaded so far, see
 * RateLimitsPage.tsx's docstring for why this can't sort the full
 * keyspace server-side. */
export function sortRateLimitEntries(entries: RateLimitEntry[], sort: SortState): RateLimitEntry[] {
    const getValue = SORT_VALUE[sort.key];
    if (!getValue) return entries;

    const direction = sort.direction === "asc" ? 1 : -1;
    return [...entries].sort((a, b) => {
        const va = getValue(a);
        const vb = getValue(b);
        if (va < vb) return -1 * direction;
        if (va > vb) return 1 * direction;
        return 0;
    });
}
