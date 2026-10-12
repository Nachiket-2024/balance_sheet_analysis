import { useQuery } from "@tanstack/react-query";

import { listRateLimitsApi } from "../api/rate_limits_api";

export const RATE_LIMITS_QUERY_KEY = ["rate-limits"] as const;

export interface RateLimitsFilters {
    scope?: "ip" | "account" | "email";
    endpoint?: string;
    identifier?: string;
    kind?: "at_limit" | "login_lockouts";
    sortBy?: "endpoint" | "scope" | "identifier" | "count" | "resets_at";
    sortDir?: "asc" | "desc";
}

// Matches rate_limiter_service.py's _SCAN_SNAPSHOT_TTL_SECONDS: polling
// faster wouldn't show anything new, since the backend serves the same
// cached SCAN snapshot within that window anyway.
const POLL_INTERVAL_MS = 5000;

/**
 * Numbered-page pagination, same shape as the audit log's queries: the
 * backend walks the matching Valkey keyspace to compute a real total and
 * slice out one page, instead of a Prev/Next-only cursor.
 *
 * keepPreviousData: without it, switching pages briefly flashes the loading
 * skeleton over an otherwise-unchanged table, which reads as a bigger change
 * than moving one page actually is. It also keeps a poll's background
 * refetch silent, so counters update in place instead of flashing the whole
 * table back to loading every 5s.
 *
 * refetchIntervalInBackground defaults to false: polling pauses while the
 * tab isn't visible and resumes (with an immediate refetch) once it regains
 * focus.
 */
export function useRateLimitsQuery(page: number, pageSize: number, filters: RateLimitsFilters = {}) {
    return useQuery({
        queryKey: [...RATE_LIMITS_QUERY_KEY, page, pageSize, filters],
        queryFn: async () => {
            const res = await listRateLimitsApi({ page, pageSize, ...filters });
            return res.data;
        },
        refetchInterval: POLL_INTERVAL_MS,
    });
}
