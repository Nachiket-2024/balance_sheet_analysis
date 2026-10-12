import api from "./axiosInstance";

/** Mirrors backend/mystic_auth/authorization/schemas/bulk_schema.py's
 * BulkItemResult/BulkResponse - one outcome per (user, target) item in a
 * bulk request, best-effort: valid items commit, invalid ones report an
 * error here instead of failing the whole batch. */
export interface BulkItemResult {
    user_email: string;
    identifier: string;
    status: "success" | "already_held" | "error";
    error: string | null;
}

export interface BulkResponse {
    results: BulkItemResult[];
    success_count: number;
    error_count: number;
}

export const bulkAssignPoliciesApi = (userEmails: string[], policyName: string) =>
    api.post<BulkResponse>("/authorization/bulk/policies/assign", {
        items: userEmails.map((user_email) => ({ user_email, policy_name: policyName })),
    });

export const bulkRemovePoliciesApi = (userEmails: string[], policyName: string) =>
    api.post<BulkResponse>("/authorization/bulk/policies/remove", {
        items: userEmails.map((user_email) => ({ user_email, policy_name: policyName })),
    });

export const bulkAssignPermissionsApi = (
    userEmails: string[],
    action: string,
    resourceType: string,
    conditions?: Record<string, unknown>
) =>
    api.post<BulkResponse>("/authorization/bulk/permissions/assign", {
        items: userEmails.map((user_email) => ({
            user_email, action, resource_type: resourceType, conditions,
        })),
    });

export const bulkRemovePermissionsApi = (userEmails: string[], action: string, resourceType: string) =>
    api.post<BulkResponse>("/authorization/bulk/permissions/remove", {
        items: userEmails.map((user_email) => ({ user_email, action, resource_type: resourceType })),
    });

export const bulkUpdateRoleApi = (userEmails: string[], role: string) =>
    api.post<BulkResponse>("/authorization/bulk/users/role", {
        items: userEmails.map((user_email) => ({ user_email, role })),
    });
