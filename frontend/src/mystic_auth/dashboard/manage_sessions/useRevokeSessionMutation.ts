import { useMutation } from "@tanstack/react-query";

import { revokeSessionApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../../auth/current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "./useSessionsQuery";
import translations from "../../translations/translations";

// Deliberately uses invalidateQueries (a background refetch), not
// useLogoutAllMutation/useLogoutMutation's setQueryData(..., null): that
// call is what actually signs this browser out (useAuthStore reads a null
// current-user as logged-out), and revoking a DIFFERENT device's session
// must never do that. Invalidating just refetches GET /auth/me so its
// active_sessions count picks up the change - without it, the dashboard's
// "Active sessions" stat kept showing the pre-revoke count (a stale cached
// /auth/me response) until something unrelated happened to refetch it.
export function useRevokeSessionMutation() {
    return useMutation<{ message: string }, Error, number>({
        mutationFn: async (sessionId: number) => {
            try {
                const res = await revokeSessionApi(sessionId);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, translations.t("dashboard:manageSessions.failedEndSession")), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
        },
    });
}
