/** Mirrors audit_log/auditLogListConfig.ts's totalPagesFor, but takes page
 * size as a parameter since RateLimitsPage uses a smaller one (10 vs. the
 * audit log's 25) to fit one viewport without DataTable's scroll area
 * kicking in. */
export function totalPagesFor(total: number, pageSize: number): number {
    return Math.max(1, Math.ceil(total / pageSize));
}
