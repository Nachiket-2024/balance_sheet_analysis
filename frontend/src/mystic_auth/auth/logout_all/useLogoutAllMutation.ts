import { useMutation } from "@tanstack/react-query";

import { logoutAllApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { useAuthStore } from "../../store/authStore";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "../../dashboard/manage_sessions/useSessionsQuery";
import { MY_POLICIES_QUERY_KEY } from "../../policies/policyQueries";
import { MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY } from "../../audit_log/authorization_log/authorizationLogQueries";
import { MY_SECURITY_AUDIT_LOG_QUERY_KEY } from "../../audit_log/security_log/securityLogQueries";
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
            // Removed, not just invalidated: see useLogoutMutation's
            // identical comment for why every "me"-scoped query needs this.
            queryClient.removeQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.removeQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            queryClient.removeQueries({ queryKey: MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY });
            queryClient.removeQueries({ queryKey: MY_SECURITY_AUDIT_LOG_QUERY_KEY });
        },
    });
}
