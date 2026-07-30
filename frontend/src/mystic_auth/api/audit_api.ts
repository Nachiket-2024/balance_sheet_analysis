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

export const getAuthorizationAuditLogApi = (limit = 50, offset = 0) =>
    api.get<AuthorizationAuditLogEntryRead[]>("/authorization/audit-log", { params: { limit, offset } });

export const getMyAuthorizationAuditLogApi = (limit = 50, offset = 0) =>
    api.get<AuthorizationAuditLogEntryRead[]>("/authorization/audit-log/me", { params: { limit, offset } });

export const getUserAuthorizationAuditLogApi = (userEmail: string, limit = 50, offset = 0) =>
    api.get<AuthorizationAuditLogEntryRead[]>(
        `/authorization/audit-log/users/${encodeURIComponent(userEmail)}`,
        { params: { limit, offset } }
    );

export const getSecurityAuditLogApi = (limit = 50, offset = 0) =>
    api.get<SecurityAuditLogEntryRead[]>("/audit/security-log", { params: { limit, offset } });

export const getMySecurityAuditLogApi = (limit = 50, offset = 0) =>
    api.get<SecurityAuditLogEntryRead[]>("/audit/security-log/me", { params: { limit, offset } });
