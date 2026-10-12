import { useQuery } from "@tanstack/react-query";

import { getMySessionsApi } from "../api/auth_api";

export const SESSIONS_QUERY_KEY = ["sessions", "me"] as const;

// Same reasoning as useCurrentUserQuery's own REVALIDATE_INTERVAL_MS: logging
// in on another device doesn't invalidate this query, so without its own
// poll the list could go stale while the "Active sessions" stat above it
// (which does poll) has already moved on. This is just a fallback:
// useSessionEventsStream.ts (SSE) invalidates it in real time, so the poll
// only needs to cover a silently dropped connection.
const REVALIDATE_INTERVAL_MS = 2 * 60 * 1000;

/** The current user's own active login sessions (Manage Sessions card),
 * newest last_used_at first, see GET /auth/sessions. */
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
