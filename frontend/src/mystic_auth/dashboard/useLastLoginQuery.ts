import { useQuery } from "@tanstack/react-query";

import { getMySecurityAuditLogApi } from "../api/audit_api";

export const LAST_LOGIN_QUERY_KEY = ["auditLog", "security", "me", "lastLogin"] as const;

// A successful login can be recorded under either event type depending on
// how the user signed in (see audit_log_service.py's constants), so both
// are checked and the more recent of the two wins.
const LOGIN_EVENT_TYPES = ["login_success", "oauth2_login_success"] as const;

async function fetchLatestLoginAt(eventType: string): Promise<string | null> {
    const res = await getMySecurityAuditLogApi({ limit: 1, eventType, success: true, sortDir: "desc" });
    return res.data[0]?.created_at ?? null;
}

/** The current user's most recent successful login timestamp (ISO string),
 * or null if the audit log has no record of one (e.g. a brand-new account
 * whose only session so far predates audit logging). Lives here (not
 * `dashboard/`), even though the Dashboard is its only current consumer:
 * it's an audit-log query (GET /audit/security-log/me), the same domain
 * AuditLogPage itself queries, not dashboard-owned logic. */
export function useLastLoginQuery() {
    return useQuery({
        queryKey: LAST_LOGIN_QUERY_KEY,
        queryFn: async () => {
            const timestamps = await Promise.all(LOGIN_EVENT_TYPES.map(fetchLatestLoginAt));
            const found = timestamps.filter((t): t is string => t !== null);
            if (found.length === 0) return null;
            return found.reduce((latest, current) => (current > latest ? current : latest));
        },
    });
}
