import type { AxiosResponse } from "axios";

/**
 * Shape every paged audit-log query hook resolves to, both in
 * authorization_log/authorizationLogQueries.ts and
 * security_log/securityLogQueries.ts: the two tabs'
 * result shape is identical, so this lives here once rather than in either.
 */
export interface AuditLogPageResult<T> {
    rows: T[];
    /** From the X-Total-Count response header; 0 if somehow missing rather
     * than throwing, so a transient proxy/CORS misconfig degrades to "no
     * pages" instead of crashing the page. */
    total: number;
}

export function toPageResult<T>(res: AxiosResponse<T[]>): AuditLogPageResult<T> {
    const total = Number(res.headers["x-total-count"]);
    return { rows: res.data, total: Number.isFinite(total) ? total : 0 };
}
