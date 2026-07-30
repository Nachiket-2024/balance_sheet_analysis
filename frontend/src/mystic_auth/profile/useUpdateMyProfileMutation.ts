import { useMutation } from "@tanstack/react-query";

import { updateMyProfileApi } from "../api/profile_api";
import type { UserUpdatePayload, AdminUserRead } from "../api/users_api";
import { extractApiErrorMessage } from "../api/apiError";
import { queryClient } from "../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../auth/current_user/useCurrentUserQuery";

/**
 * useUpdateMyProfileMutation
 * ----------------------------
 * PUT /users/me (name and/or password). Invalidates the current-user query
 * on success so the Zustand auth store (synced from that query via
 * useAuthSession) picks up a changed name immediately, instead of showing
 * the pre-edit value until the next full page load.
 */
export function useUpdateMyProfileMutation() {
    return useMutation<AdminUserRead, Error, UserUpdatePayload>({
        mutationFn: async (payload) => {
            try {
                return (await updateMyProfileApi(payload)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to update profile"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
        },
    });
}
