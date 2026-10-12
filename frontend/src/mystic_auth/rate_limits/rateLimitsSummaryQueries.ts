import { useQuery } from "@tanstack/react-query";

import { getRateLimitsSummaryApi } from "../api/rate_limits_api";

export const RATE_LIMITS_SUMMARY_QUERY_KEY = ["rate-limits", "summary"] as const;

export function useRateLimitsSummaryQuery() {
    return useQuery({
        queryKey: RATE_LIMITS_SUMMARY_QUERY_KEY,
        queryFn: async () => (await getRateLimitsSummaryApi()).data,
        refetchInterval: 5000,
    });
}
