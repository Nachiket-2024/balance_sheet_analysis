import api from "./axiosInstance";

export interface RateLimitEntry {
    key: string;
    endpoint: string;
    // "email" is login_protection_service's login_lock:email:{email}
    // counter - the actual per-account login brute-force lockout, distinct
    // from rate_limiter_service's own "account" scope (see
    // rate_limiter_service.list_active_limits).
    scope: "ip" | "account" | "email";
    identifier: string;
    count: number;
    limit: number;
    resets_in_seconds: number | null;
}

export interface RateLimitPage {
    entries: RateLimitEntry[];
    total: number;
    // The keyspace walk backing this page hit its cap (see rate_limiter_
    // service.py's MAX_SCANNED_KEYS) before reaching the end: `total`, and
    // any page count derived from it, is a floor, not an exact count.
    truncated: boolean;
}

export interface RateLimitSummary {
    total: number;
    at_limit: number;
    login_lockouts: number;
    by_endpoint: Record<string, number>;
    by_scope: Record<string, number>;
    truncated: boolean;
}

export interface ListRateLimitsParams {
    page?: number;
    scope?: "ip" | "account" | "email";
    endpoint?: string;
    identifier?: string;
    pageSize?: number;
    kind?: "at_limit" | "login_lockouts";
    sortBy?: "endpoint" | "scope" | "identifier" | "count" | "resets_at";
    sortDir?: "asc" | "desc";
}

export const listRateLimitsApi = ({ page = 1, scope, endpoint, identifier, pageSize, kind, sortBy, sortDir }: ListRateLimitsParams = {}) =>
    api.get<RateLimitPage>("/rate-limits/", {
        params: { page, scope, endpoint: endpoint || undefined, identifier: identifier || undefined, page_size: pageSize, kind, sort_by: sortBy, sort_dir: sortDir },
    });

export const getRateLimitsSummaryApi = () => api.get<RateLimitSummary>("/rate-limits/summary");

// key is the raw Valkey key (endpoint:scope:identifier, e.g. "login:ip:1.2.3.4")
// - encoded whole since it contains colons but no slashes.
export const resetRateLimitApi = (key: string) => api.delete(`/rate-limits/${encodeURIComponent(key)}`);
