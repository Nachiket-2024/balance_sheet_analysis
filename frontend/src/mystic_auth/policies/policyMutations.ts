import { useMutation } from "@tanstack/react-query";

import {
    createPolicyApi,
    updatePolicyApi,
    deletePolicyApi,
    assignPolicyApi,
    revokePolicyApi,
    type PolicyCreatePayload,
    type PolicyUpdatePayload,
    type PolicyRead,
} from "../api/policies_api";
import { extractApiErrorMessage } from "../api/apiError";
import { queryClient } from "../core/queryClient";
import { useAuthStore } from "../store/authStore";
import { CURRENT_USER_QUERY_KEY } from "../auth/current_user/useCurrentUserQuery";
import { POLICIES_QUERY_KEY, userPoliciesQueryKey, MY_POLICIES_QUERY_KEY } from "./policyQueries";

/**
 * useCreatePolicyMutation / useUpdatePolicyMutation / useDeletePolicyMutation
 * ----------------------------
 * Each invalidates the shared policies list on success so the Policy
 * Management page always reflects the backend's current state rather than
 * a stale cached list. TanStack Query owns this cache, not local state.
 */
export function useCreatePolicyMutation() {
    return useMutation<PolicyRead, Error, PolicyCreatePayload>({
        mutationFn: async (payload) => {
            try {
                return (await createPolicyApi(payload)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to create policy"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: POLICIES_QUERY_KEY });
        },
    });
}

export function useUpdatePolicyMutation() {
    return useMutation<PolicyRead, Error, { policyName: string; payload: PolicyUpdatePayload }>({
        mutationFn: async ({ policyName, payload }) => {
            try {
                return (await updatePolicyApi(policyName, payload)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to update policy"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: POLICIES_QUERY_KEY });
        },
    });
}

export function useDeletePolicyMutation() {
    return useMutation<void, Error, { policyName: string; reason?: string }>({
        mutationFn: async ({ policyName, reason }) => {
            try {
                await deletePolicyApi(policyName, reason);
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to delete policy"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: POLICIES_QUERY_KEY });
        },
    });
}

export function useAssignPolicyMutation() {
    return useMutation<unknown, Error, { userEmail: string; policyName: string }>({
        mutationFn: async ({ userEmail, policyName }) => {
            try {
                return (await assignPolicyApi(userEmail, policyName)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to assign policy"), { cause: error });
            }
        },
        onSuccess: (_data, { userEmail }) => {
            queryClient.invalidateQueries({ queryKey: userPoliciesQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            // If the caller just changed their OWN policies, the Zustand
            // permissions cache (populated from this same query, see
            // useAuthSession) would otherwise stay stale until the next
            // reload or 401, leaving IfCan/ProtectedRoute checks acting on
            // a permission set that no longer matches the backend.
            if (userEmail === useAuthStore.getState().email) {
                queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
            }
        },
    });
}

export function useRevokePolicyMutation() {
    return useMutation<unknown, Error, { userEmail: string; policyName: string }>({
        mutationFn: async ({ userEmail, policyName }) => {
            try {
                return (await revokePolicyApi(userEmail, policyName)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to revoke policy"), { cause: error });
            }
        },
        onSuccess: (_data, { userEmail }) => {
            queryClient.invalidateQueries({ queryKey: userPoliciesQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            // See useAssignPolicyMutation's onSuccess above for why.
            if (userEmail === useAuthStore.getState().email) {
                queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
            }
        },
    });
}
