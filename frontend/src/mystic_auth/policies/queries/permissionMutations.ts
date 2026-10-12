import { useMutation } from "@tanstack/react-query";

import { grantPermissionApi, revokePermissionApi, type PermissionAssignmentPayload } from "../../api/permissions_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { queryClient } from "../../core/queryClient";
import { useAuthStore } from "../../store/authStore";
import { CURRENT_USER_QUERY_KEY } from "../../auth/current_user/useCurrentUserQuery";
import { markSelfPermissionMutation } from "../../auth/session_lifecycle/selfPermissionMutationGuard";
import { MY_PERMISSIONS_QUERY_KEY, PERMISSION_CATALOG_USAGE_QUERY_KEY, userPermissionsQueryKey } from "./permissionQueries";

/**
 * useGrantPermissionMutation / useRevokePermissionMutation
 * ----------------------------
 * Direct (bypasses-Policy) grant/revoke, the granular counterpart to
 * useAssignPolicyMutation/useRevokePolicyMutation (policyMutations.ts).
 * Same invalidation shape, including the self-grant CURRENT_USER_QUERY_KEY
 * refresh and selfPermissionMutationGuard arming (see that file's onSuccess
 * comment for why).
 */
export function useGrantPermissionMutation() {
    return useMutation<unknown, Error, { userEmail: string } & PermissionAssignmentPayload>({
        mutationFn: async ({ userEmail, ...payload }) => {
            try {
                return (await grantPermissionApi(userEmail, payload)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to grant permission"), { cause: error });
            }
        },
        onSuccess: (_data, { userEmail }) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: userPermissionsQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_PERMISSIONS_QUERY_KEY });
            if (userEmail === useAuthStore.getState().email) {
                queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
                markSelfPermissionMutation();
            }
        },
    });
}

export function useRevokePermissionMutation() {
    return useMutation<unknown, Error, { userEmail: string; action: string; resourceType: string }>({
        mutationFn: async ({ userEmail, action, resourceType }) => {
            try {
                return (await revokePermissionApi(userEmail, action, resourceType)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to revoke permission"), { cause: error });
            }
        },
        onSuccess: (_data, { userEmail }) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: userPermissionsQueryKey(userEmail) });
            queryClient.invalidateQueries({ queryKey: MY_PERMISSIONS_QUERY_KEY });
            if (userEmail === useAuthStore.getState().email) {
                queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
                markSelfPermissionMutation();
            }
        },
    });
}
