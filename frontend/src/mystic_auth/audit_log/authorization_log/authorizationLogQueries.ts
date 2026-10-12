import { useQuery } from "@tanstack/react-query";

import {
    getAuthorizationAuditLogApi,
    getMyAuthorizationAuditLogApi,
    getUserAuthorizationAuditLogApi,
} from "../../api/audit_api";
import type { SortDirection } from "../../ui/hooks/useSortState";
import { toPageResult } from "../auditLogPageResult";

export const AUTHORIZATION_AUDIT_LOG_QUERY_KEY = ["auditLog", "authorization", "all"] as const;
export const MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY = ["auditLog", "authorization", "me"] as const;
export const userAuthorizationAuditLogQueryKey = (userEmail: string) =>
    ["auditLog", "authorization", "user", userEmail] as const;

export interface AuthorizationLogFilters {
    search?: string;
    action?: string;
    resourceType?: string;
    allowed?: boolean;
    sortBy?: string;
    sortDir?: SortDirection;
    from?: string;
    to?: string;
}

// Every hook below pages via limit/offset (offset = (page-1)*pageSize) and keeps the previous
// page's rows on screen while the next loads (keepPreviousData), same as userQueries.ts's
// useUsersQuery, so the table doesn't flash a loading skeleton on every page/sort/filter change.

export function useAuthorizationAuditLogQuery(page: number, pageSize: number, filters: AuthorizationLogFilters = {}) {
    return useQuery({
        queryKey: [...AUTHORIZATION_AUDIT_LOG_QUERY_KEY, page, pageSize, filters],
        queryFn: async () =>
            toPageResult(
                await getAuthorizationAuditLogApi({ limit: pageSize, offset: (page - 1) * pageSize, ...filters })
            ),
    });
}

export function useMyAuthorizationAuditLogQuery(
    page: number, pageSize: number, filters: Omit<AuthorizationLogFilters, "search"> = {}
) {
    return useQuery({
        queryKey: [...MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY, page, pageSize, filters],
        queryFn: async () =>
            toPageResult(
                await getMyAuthorizationAuditLogApi({ limit: pageSize, offset: (page - 1) * pageSize, ...filters })
            ),
    });
}

export function useUserAuthorizationAuditLogQuery(userEmail: string, page: number, pageSize: number, enabled = true) {
    return useQuery({
        queryKey: [...userAuthorizationAuditLogQueryKey(userEmail), page, pageSize],
        queryFn: async () =>
            toPageResult(
                await getUserAuthorizationAuditLogApi(userEmail, { limit: pageSize, offset: (page - 1) * pageSize })
            ),
        enabled: enabled && !!userEmail,
    });
}
