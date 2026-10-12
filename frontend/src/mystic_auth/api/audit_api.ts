import api from "./axiosInstance";

export interface AuthorizationAuditLogEntryRead {
    id: number;
    user_email: string;
    action: string;
    resource_type: string;
    resource_identifier: string | null;
    allowed: boolean;
    candidate_policy_names: string[];
    granting_policy_names: string[];
    failed_conditions: Record<string, string[]> | null;
    context: Record<string, unknown> | null;
    created_at: string;
}

export interface SecurityAuditLogEntryRead {
    id: number;
    user_email: string | null;
    event_type: string;
    success: boolean;
    ip_address: string | null;
    user_agent: string | null;
    request_id: string | null;
    event_metadata: Record<string, unknown> | null;
    created_at: string;
}

interface BaseListParams {
    limit?: number;
    offset?: number;
    /** user_email substring match. Only meaningful on the "all users" endpoints below;
     * each /me endpoint is already scoped to the caller's own email. */
    search?: string;
    /** Column to sort by. Must be one of the backend's allowlisted sortable columns
     * (see the audit log repositories' `_SORTABLE_COLUMNS`); anything else is ignored
     * server-side and falls back to created_at. */
    sortBy?: string;
    sortDir?: "asc" | "desc";
    /** ISO 8601 datetime bounds (inclusive), for the time-range picker (TimeRangeControl.tsx).
     * Omit both for no lower/upper bound. */
    from?: string;
    to?: string;
}

export interface AuthorizationAuditLogListParams extends BaseListParams {
    /** Exact match, e.g. one of PERMISSIONS' values. */
    action?: string;
    /** Exact match, e.g. one of AUTHORIZATION_RESOURCE_TYPES. */
    resourceType?: string;
    allowed?: boolean;
}

export interface SecurityAuditLogListParams extends BaseListParams {
    /** Exact match, one of SECURITY_EVENT_TYPES. */
    eventType?: string;
    /** Substring match - IPs aren't a fixed vocabulary. */
    ipAddress?: string;
    success?: boolean;
}

function toAuthorizationParams({
    limit = 50, offset = 0, search, action, resourceType, allowed, sortBy, sortDir, from, to,
}: AuthorizationAuditLogListParams) {
    return {
        limit, offset, search, action, resource_type: resourceType, allowed, sort_by: sortBy, sort_dir: sortDir,
        from, to,
    };
}

function toSecurityParams({
    limit = 50, offset = 0, search, eventType, ipAddress, success, sortBy, sortDir, from, to,
}: SecurityAuditLogListParams) {
    return {
        limit, offset, search, event_type: eventType, ip_address: ipAddress, success, sort_by: sortBy, sort_dir: sortDir,
        from, to,
    };
}

export const getAuthorizationAuditLogApi = (params: AuthorizationAuditLogListParams = {}) =>
    api.get<AuthorizationAuditLogEntryRead[]>("/authorization/audit-log", { params: toAuthorizationParams(params) });

export const getMyAuthorizationAuditLogApi = (params: AuthorizationAuditLogListParams = {}) =>
    api.get<AuthorizationAuditLogEntryRead[]>("/authorization/audit-log/me", { params: toAuthorizationParams(params) });

export const getUserAuthorizationAuditLogApi = (userEmail: string, params: AuthorizationAuditLogListParams = {}) =>
    api.get<AuthorizationAuditLogEntryRead[]>(
        `/authorization/audit-log/users/${encodeURIComponent(userEmail)}`,
        { params: toAuthorizationParams(params) }
    );

export const getSecurityAuditLogApi = (params: SecurityAuditLogListParams = {}) =>
    api.get<SecurityAuditLogEntryRead[]>("/audit/security-log", { params: toSecurityParams(params) });

export const getMySecurityAuditLogApi = (params: SecurityAuditLogListParams = {}) =>
    api.get<SecurityAuditLogEntryRead[]>("/audit/security-log/me", { params: toSecurityParams(params) });

/** A specific user's security events - the permission-scoped counterpart to
 * getMySecurityAuditLogApi, gated on security_audit:read. Pass
 * eventType: "access_change" (a UI-only alias the backend expands, see
 * backend/mystic_auth/audit_log/audit_log_repository.py's _apply_filters) to get only the events that
 * represent a permission holder changing this user's access (policy/permission/role),
 * not their own auth activity - backs UserAccessDialog's Details tab. */
export const getUserSecurityAuditLogApi = (userEmail: string, params: SecurityAuditLogListParams = {}) =>
    api.get<SecurityAuditLogEntryRead[]>(
        `/audit/security-log/users/${encodeURIComponent(userEmail)}`,
        { params: toSecurityParams(params) }
    );

export interface LoginTrendPoint {
    date: string;
    success: number;
    failure: number;
}

/** `search` follows the page's own email search (all-users trend only - the "me" trend below is
 * already scoped to one user, so a search box there wouldn't narrow anything). */
export const getLoginTrendApi = (days = 14, search?: string, from?: string, to?: string) => {
    const params: Record<string, string | number | undefined> = { days, search };
    if (from) params.from = from;
    if (to) params.to = to;
    return api.get<LoginTrendPoint[]>("/audit/security-log/login-trend", { params });
};

export const getMyLoginTrendApi = (days = 14, from?: string, to?: string) => {
    const params: Record<string, string | number> = { days };
    if (from) params.from = from;
    if (to) params.to = to;
    return api.get<LoginTrendPoint[]>("/audit/security-log/me/login-trend", { params });
};
