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

export const listPoliciesApi = () => api.get<PolicyRead[]>("/authorization/policies");

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

export const assignPolicyApi = (userEmail: string, policyName: string) =>
    api.post(`/authorization/users/${encodeURIComponent(userEmail)}/policies`, { policy_name: policyName });

export const revokePolicyApi = (userEmail: string, policyName: string) =>
    api.delete(
        `/authorization/users/${encodeURIComponent(userEmail)}/policies/${encodeURIComponent(policyName)}`
    );

export const getMyPoliciesApi = () => api.get<UserPoliciesRead>("/authorization/users/me/policies");

export const getUserPoliciesApi = (userEmail: string) =>
    api.get<UserPoliciesRead>(`/authorization/users/${encodeURIComponent(userEmail)}/policies`);
