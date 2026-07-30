import { useMutation } from "@tanstack/react-query";

import { logoutAllApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { useAuthStore } from "../../store/authStore";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import type { LogoutResponse } from "../logout/logout_types";

// Same reasoning as useLogoutMutation: setAuthenticated(false), not
// reset() (see that file's comment for why).
export function useLogoutAllMutation() {
    return useMutation<LogoutResponse, Error, void>({
        mutationFn: async () => {
            try {
                const res = await logoutAllApi();
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Logout all devices failed"), { cause: error });
            }
        },
        onSuccess: () => {
            useAuthStore.getState().setAuthenticated(false);
            queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
        },
    });
}
