import { useMutation } from "@tanstack/react-query";

import { logoutApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { useAuthStore } from "../../store/authStore";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import type { LogoutResponse } from "./logout_types";

// Marks the auth store unauthenticated immediately rather than waiting on a
// currentUser refetch that would 401 by design. Deliberately
// `setAuthenticated(false)`, not `reset()`: `reset()` puts isAuthenticated
// back to null, which ProtectedRoute reads as "still checking the session"
// (spinner) rather than "log out now" (immediate redirect).
export function useLogoutMutation() {
    return useMutation<LogoutResponse, Error, void>({
        mutationFn: async () => {
            try {
                const res = await logoutApi();
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Logout failed"), { cause: error });
            }
        },
        onSuccess: () => {
            useAuthStore.getState().setAuthenticated(false);
            queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
        },
    });
}
