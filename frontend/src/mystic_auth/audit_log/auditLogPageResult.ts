import type { AxiosResponse } from "axios";

/**
 * Shape every paged audit-log query hook resolves to (authorization_log/authorizationLogQueries.ts
 * and security_log/securityLogQueries.ts share this shape, so it lives here once).
 */
export interface AuditLogPageResult<T> {
    rows: T[];
    /** From the X-Total-Count response header; 0 if missing rather than throwing, so a
     * transient proxy/CORS misconfig degrades to "no pages" instead of crashing the page. */
    total: number;
}

export function toPageResult<T>(res: AxiosResponse<T[]>): AuditLogPageResult<T> {
    const total = Number(res.headers["x-total-count"]);
    return { rows: res.data, total: Number.isFinite(total) ? total : 0 };
}
