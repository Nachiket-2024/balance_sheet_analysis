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
    /** user_email substring match. Only meaningful for the "all users"
     * endpoints below - each /me endpoint is already scoped to the
     * caller's own single email. */
    search?: string;
    /** Column to sort by; must be one of the backend's own allowlisted
     * sortable columns for that log type (see the two audit log
     * repositories' `_SORTABLE_COLUMNS`) - any other value is ignored
     * server-side and falls back to created_at. */
    sortBy?: string;
    sortDir?: "asc" | "desc";
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
    limit = 50, offset = 0, search, action, resourceType, allowed, sortBy, sortDir,
}: AuthorizationAuditLogListParams) {
    return {
        limit, offset, search, action, resource_type: resourceType, allowed, sort_by: sortBy, sort_dir: sortDir,
    };
}

function toSecurityParams({
    limit = 50, offset = 0, search, eventType, ipAddress, success, sortBy, sortDir,
}: SecurityAuditLogListParams) {
    return {
        limit, offset, search, event_type: eventType, ip_address: ipAddress, success, sort_by: sortBy, sort_dir: sortDir,
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

export interface LoginTrendPoint {
    date: string;
    success: number;
    failure: number;
}

export const getLoginTrendApi = (days = 14) =>
    api.get<LoginTrendPoint[]>("/audit/security-log/login-trend", { params: { days } });

export const getMyLoginTrendApi = (days = 14) =>
    api.get<LoginTrendPoint[]>("/audit/security-log/me/login-trend", { params: { days } });
