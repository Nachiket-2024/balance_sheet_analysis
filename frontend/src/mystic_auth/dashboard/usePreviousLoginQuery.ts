import { useQuery } from "@tanstack/react-query";

import { getMySecurityAuditLogApi } from "../api/audit_api";
import type { SecurityAuditLogEntryRead } from "../api/audit_api";

export const PREVIOUS_LOGIN_QUERY_KEY = ["auditLog", "security", "me", "previousLogin"] as const;

// A login is recorded under one of two event types depending on how the
// user signed in, so both are checked and merged.
const LOGIN_EVENT_TYPES = ["login_success", "oauth2_login_success"] as const;

export type PreviousLogin = Pick<SecurityAuditLogEntryRead, "created_at" | "ip_address" | "user_agent">;

async function fetchRecentLogins(eventType: string): Promise<SecurityAuditLogEntryRead[]> {
    const res = await getMySecurityAuditLogApi({ limit: 2, eventType, success: true, sortDir: "desc" });
    return res.data;
}

/** The login before the most recent one, or null if there's only been one.
 * The most recent login is almost always the one that started this visit, so
 * showing it would just echo "a few seconds ago" back to the user. */
export function usePreviousLoginQuery() {
    return useQuery({
        queryKey: PREVIOUS_LOGIN_QUERY_KEY,
        queryFn: async (): Promise<PreviousLogin | null> => {
            const results = await Promise.all(LOGIN_EVENT_TYPES.map(fetchRecentLogins));
            const logins = results.flat().sort((a, b) => b.created_at.localeCompare(a.created_at));
            const previous = logins[1];
            if (!previous) return null;
            return { created_at: previous.created_at, ip_address: previous.ip_address, user_agent: previous.user_agent };
        },
    });
}
