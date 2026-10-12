import api from "./axiosInstance";

export interface PolicyRead {
    id: number;
    name: string;
    description: string | null;
    actions: string[];
    resource_type: string;
    conditions: Record<string, unknown> | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
    created_by: string | null;
    holder_count?: number;
}

export interface PolicyCreatePayload {
    name: string;
    description?: string;
    actions: string[];
    resource_type: string;
    conditions?: Record<string, unknown>;
}

export interface PolicyUpdatePayload {
    name?: string;
    description?: string;
    actions?: string[];
    resource_type?: string;
    conditions?: Record<string, unknown>;
    is_active?: boolean;
    change_reason?: string;
}

export interface PolicyHistoryEntryRead {
    id: number;
    policy_id: number;
    policy_name: string;
    change_type: string;
    previous_definition: Record<string, unknown> | null;
    new_definition: Record<string, unknown> | null;
    changed_fields: string[] | null;
    changed_by: string | null;
    change_reason: string | null;
    created_at: string;
}

export interface UserPoliciesRead {
    user_email: string;
    policies: PolicyRead[];
}

export interface PolicyHolderRead {
    email: string;
    name: string;
    role: string | null;
    assigned_at: string;
    assigned_by: string | null;
}

export interface ListPoliciesParams {
    limit?: number;
    offset?: number;
    search?: string;
    /** Exact match, e.g. one of AUTHORIZATION_RESOURCE_TYPES. */
    resourceType?: string;
    isActive?: boolean;
    /** Exact match against one entry in the policy's actions array, e.g.
     * "invoices:void" - answers "which policies grant this action". */
    containsAction?: string;
    destructiveOnly?: boolean;
    /** Column to sort by. Must be one of the backend's allowlisted sortable columns
     * (see policy_repository.py's _SORTABLE_COLUMN_NAMES); anything else is ignored
     * server-side and falls back to id. */
    sortBy?: string;
    sortDir?: "asc" | "desc";
}

function toListPoliciesApiParams({
    limit = 1000, offset = 0, search, resourceType, isActive, containsAction, destructiveOnly, sortBy, sortDir,
}: ListPoliciesParams) {
    return {
        limit, offset, search, resource_type: resourceType, is_active: isActive,
        contains_action: containsAction, destructive_only: destructiveOnly, sort_by: sortBy, sort_dir: sortDir,
    };
}

// Total matching row count rides the X-Total-Count response header (same pattern as
// listUsersApi), which policyQueries.ts's paginated hook reads for the page count.
// Called with no params, this returns the full unfiltered list (used by
// UserPoliciesDialog's "assign a policy" dropdown, which wants every policy).
export const listPoliciesApi = (params: ListPoliciesParams = {}) =>
    api.get<PolicyRead[]>("/authorization/policies", { params: toListPoliciesApiParams(params) });

export const getPolicyApi = (policyName: string) =>
    api.get<PolicyRead>(`/authorization/policies/${encodeURIComponent(policyName)}`);

export const createPolicyApi = (payload: PolicyCreatePayload) =>
    api.post<PolicyRead>("/authorization/policies", payload);

export const updatePolicyApi = (policyName: string, payload: PolicyUpdatePayload) =>
    api.put<PolicyRead>(`/authorization/policies/${encodeURIComponent(policyName)}`, payload);

export const deletePolicyApi = (policyName: string, reason?: string) =>
    api.delete(`/authorization/policies/${encodeURIComponent(policyName)}`, { params: { reason } });

export const getPolicyHistoryApi = (policyName: string, limit = 50, offset = 0) =>
    api.get<PolicyHistoryEntryRead[]>(`/authorization/policies/${encodeURIComponent(policyName)}/history`, {
        params: { limit, offset },
    });

export const rollbackPolicyApi = (policyName: string, historyId: number, reason?: string) =>
    api.post<PolicyRead>(
        `/authorization/policies/${encodeURIComponent(policyName)}/history/${historyId}/rollback`,
        reason ? { reason } : {},
    );

export const assignPolicyApi = (userEmail: string, policyName: string) =>
    api.post(`/authorization/users/${encodeURIComponent(userEmail)}/policies`, { policy_name: policyName });

export const revokePolicyApi = (userEmail: string, policyName: string) =>
    api.delete(
        `/authorization/users/${encodeURIComponent(userEmail)}/policies/${encodeURIComponent(policyName)}`
    );

// Revokes one action from a user's policy assignment while keeping the policy's other
// actions (converted to direct grants server-side, see policy_action_revocation_service.py).
// Unlike revokePolicyApi, it never touches the Policy row, so other holders are unaffected.
export const revokePolicyActionApi = (userEmail: string, policyName: string, action: string) =>
    api.post(
        `/authorization/users/${encodeURIComponent(userEmail)}/policies/${encodeURIComponent(policyName)}/revoke-action`,
        { action }
    );

// Backs both the details dialog's "Assigned users" list and the delete
// confirm's "N users will lose access" count (frontend takes .length).
export const getPolicyHoldersApi = (policyName: string) =>
    api.get<PolicyHolderRead[]>(`/authorization/policies/${encodeURIComponent(policyName)}/holders`);

export const getMyPoliciesApi = () => api.get<UserPoliciesRead>("/authorization/users/me/policies");

export const getUserPoliciesApi = (userEmail: string) =>
    api.get<UserPoliciesRead>(`/authorization/users/${encodeURIComponent(userEmail)}/policies`);
