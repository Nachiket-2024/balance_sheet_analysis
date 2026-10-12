import { useMutation } from "@tanstack/react-query";

import {
    createPolicyApi,
    updatePolicyApi,
    deletePolicyApi,
    assignPolicyApi,
    revokePolicyApi,
    revokePolicyActionApi,
    rollbackPolicyApi,
    type PolicyCreatePayload,
    type PolicyUpdatePayload,
    type PolicyRead,
} from "../../api/policies_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { queryClient } from "../../core/queryClient";
import { useAuthStore } from "../../store/authStore";
import { CURRENT_USER_QUERY_KEY } from "../../auth/current_user/useCurrentUserQuery";
import { markSelfPermissionMutation } from "../../auth/session_lifecycle/selfPermissionMutationGuard";
import { POLICIES_QUERY_KEY, userPoliciesQueryKey, MY_POLICIES_QUERY_KEY } from "./policyQueries";
import { userPermissionsQueryKey, MY_PERMISSIONS_QUERY_KEY, PERMISSION_CATALOG_USAGE_QUERY_KEY } from "./permissionQueries";

/**
 * useCreatePolicyMutation / useUpdatePolicyMutation / useDeletePolicyMutation
 * ----------------------------
 * Each invalidates the shared policies list on success so the Policy
 * Management page reflects the backend's current state, not a stale cache.
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
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
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
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
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
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: POLICIES_QUERY_KEY });
        },
    });
}

export function useRollbackPolicyMutation() {
    return useMutation<PolicyRead, Error, { policyName: string; historyId: number; reason?: string }>({
        mutationFn: async ({ policyName, historyId, reason }) => {
            try {
                return (await rollbackPolicyApi(policyName, historyId, reason)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to roll back policy"), { cause: error });
            }
        },
        onSuccess: (_data, { policyName }) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: POLICIES_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: ["policies", policyName, "history"] });
        },
    });
}

/**
 * useAssignPolicyMutation / useRevokePolicyMutation
 * ----------------------------
 * Invalidates UserPoliciesDialog's cached policy list on success so it
 * reflects the backend's confirmed state.
 */
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
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: userPoliciesQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            // If the caller changed their OWN policies, the Zustand
            // permissions cache (populated from this query, see
            // useAuthSession) would otherwise stay stale until the next
            // reload or 401, leaving IfCan/ProtectedRoute checks acting on
            // permissions the backend no longer grants.
            if (userEmail === useAuthStore.getState().email) {
                queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
                // Arms selfPermissionMutationGuard so this tab's own
                // "permissions_changed" SSE echo (see useSessionEventsStream.ts)
                // doesn't get read as a live revoke before the invalidation
                // above resolves.
                markSelfPermissionMutation();
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
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: userPoliciesQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            // See useAssignPolicyMutation's onSuccess above for why.
            if (userEmail === useAuthStore.getState().email) {
                queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
                markSelfPermissionMutation();
            }
        },
    });
}

/**
 * useRevokePolicyActionMutation
 * ----------------------------
 * Carves one action out of a user's policy assignment (see
 * revokePolicyActionApi's docstring): the policy's other actions survive,
 * converted server-side into direct grants, so both the assigned-policies
 * list and the direct-permissions list can change. Invalidates both.
 */
export function useRevokePolicyActionMutation() {
    return useMutation<unknown, Error, { userEmail: string; policyName: string; action: string }>({
        mutationFn: async ({ userEmail, policyName, action }) => {
            try {
                return (await revokePolicyActionApi(userEmail, policyName, action)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to revoke action"), { cause: error });
            }
        },
        onSuccess: (_data, { userEmail }) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: userPoliciesQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: userPermissionsQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_PERMISSIONS_QUERY_KEY });
            if (userEmail === useAuthStore.getState().email) {
                queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
                markSelfPermissionMutation();
            }
        },
    });
}
