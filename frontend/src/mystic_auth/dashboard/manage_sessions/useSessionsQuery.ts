import { useQuery } from "@tanstack/react-query";

import { getMySessionsApi } from "../../api/auth_api";

export const SESSIONS_QUERY_KEY = ["sessions", "me"] as const;

// Same reasoning as useCurrentUserQuery's own REVALIDATE_INTERVAL_MS: this
// card only fetches once on mount otherwise, then relies on the shared 30s
// staleTime plus whatever happens to trigger a refetch (window focus, a
// revoke mutation invalidating it). Logging in on another device doesn't
// invalidate this query at all, so without a poll of its own the list could
// sit showing an old device count well after the "Active sessions" stat
// above it (which does poll) had already moved on - the two visibly
// disagreeing until something else happened to refresh this one.
//
// This is a fallback, not the primary mechanism - useSessionEventsStream.ts
// (SSE) invalidates this query in real time whenever a session actually
// changes, so this poll only needs to cover the rare case that connection
// silently drops.
const REVALIDATE_INTERVAL_MS = 2 * 60 * 1000;

/** The current user's own active login sessions (Manage Sessions card),
 * newest last_used_at first - see GET /auth/sessions. */
export function useSessionsQuery() {
    return useQuery({
        queryKey: SESSIONS_QUERY_KEY,
        queryFn: async () => {
            const res = await getMySessionsApi();
            return res.data;
        },
        refetchInterval: REVALIDATE_INTERVAL_MS,
        refetchIntervalInBackground: true,
    });
}
