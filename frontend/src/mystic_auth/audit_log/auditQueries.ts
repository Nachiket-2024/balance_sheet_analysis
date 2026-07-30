import { useQuery } from "@tanstack/react-query";

import {
    getAuthorizationAuditLogApi,
    getMyAuthorizationAuditLogApi,
    getUserAuthorizationAuditLogApi,
    getSecurityAuditLogApi,
    getMySecurityAuditLogApi,
} from "../api/audit_api";

export const AUTHORIZATION_AUDIT_LOG_QUERY_KEY = ["auditLog", "authorization", "all"] as const;
export const MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY = ["auditLog", "authorization", "me"] as const;
export const userAuthorizationAuditLogQueryKey = (userEmail: string) =>
    ["auditLog", "authorization", "user", userEmail] as const;
export const SECURITY_AUDIT_LOG_QUERY_KEY = ["auditLog", "security", "all"] as const;
export const MY_SECURITY_AUDIT_LOG_QUERY_KEY = ["auditLog", "security", "me"] as const;

export function useAuthorizationAuditLogQuery(limit = 50, offset = 0) {
    return useQuery({
        queryKey: [...AUTHORIZATION_AUDIT_LOG_QUERY_KEY, limit, offset],
        queryFn: async () => (await getAuthorizationAuditLogApi(limit, offset)).data,
    });
}

export function useMyAuthorizationAuditLogQuery(limit = 50, offset = 0) {
    return useQuery({
        queryKey: [...MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY, limit, offset],
        queryFn: async () => (await getMyAuthorizationAuditLogApi(limit, offset)).data,
    });
}

export function useUserAuthorizationAuditLogQuery(userEmail: string, limit = 50, offset = 0, enabled = true) {
    return useQuery({
        queryKey: [...userAuthorizationAuditLogQueryKey(userEmail), limit, offset],
        queryFn: async () => (await getUserAuthorizationAuditLogApi(userEmail, limit, offset)).data,
        enabled: enabled && !!userEmail,
    });
}

export function useSecurityAuditLogQuery(limit = 50, offset = 0) {
    return useQuery({
        queryKey: [...SECURITY_AUDIT_LOG_QUERY_KEY, limit, offset],
        queryFn: async () => (await getSecurityAuditLogApi(limit, offset)).data,
    });
}

export function useMySecurityAuditLogQuery(limit = 50, offset = 0) {
    return useQuery({
        queryKey: [...MY_SECURITY_AUDIT_LOG_QUERY_KEY, limit, offset],
        queryFn: async () => (await getMySecurityAuditLogApi(limit, offset)).data,
    });
}
