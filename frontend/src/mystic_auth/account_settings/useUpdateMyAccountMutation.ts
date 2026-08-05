import { useMutation } from "@tanstack/react-query";

import { updateMyAccountApi } from "../api/account_settings_api";
import type { UserUpdatePayload, AdminUserRead } from "../api/users_api";
import { extractApiErrorMessage } from "../api/apiError";
import { queryClient } from "../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../auth/current_user/useCurrentUserQuery";
import { trackSessionRotatingRequest } from "../auth/sessionRotationGuard";

/**
 * useUpdateMyAccountMutation
 * ----------------------------
 * PUT /users/me (name and/or password). Invalidates the current-user query
 * on success so the Zustand auth store (synced from that query via
 * useAuthSession) picks up a changed name immediately, instead of showing
 * the pre-edit value until the next full page load.
 */
export function useUpdateMyAccountMutation() {
    return useMutation<AdminUserRead, Error, UserUpdatePayload>({
        mutationFn: async (payload) => {
            try {
                // Only a password change rotates this device's session cookies
                // server-side (see sessionRotationGuard.ts) - a name-only update
                // never touches tokens, so it's not worth tracking.
                const request = updateMyAccountApi(payload);
                if (payload.password) trackSessionRotatingRequest(request);
                return (await request).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to update profile"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
        },
    });
}
