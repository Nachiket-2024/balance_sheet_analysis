import { useMutation } from "@tanstack/react-query";

import { loginApi, getCurrentUserApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { useAuthStore } from "../../store/authStore";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "../../dashboard/manage_sessions/useSessionsQuery";
import { MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY } from "../../audit_log/authorization_log/queries";
import { MY_SECURITY_AUDIT_LOG_QUERY_KEY } from "../../audit_log/security_log/queries";
import { MY_POLICIES_QUERY_KEY } from "../../policies/policyQueries";
import type { CurrentUserProfile } from "../current_user/current_user_types";
import type { LoginRequest } from "./login_types";

// mutationFn logs in, then fetches the fresh profile, so the mutation only
// resolves once the session is fully confirmed. A plain "invalidate and
// hope the query refetches in time" would risk a caller reading
// isAuthenticated before the refetch lands. onSuccess writes straight into
// the Zustand store and the shared query cache so every consumer
// (useAuthStore subscribers and the app-level useCurrentUserQuery) is
// consistent immediately, not after another round trip. Every other
// "me"-scoped query (sessions, policies, audit history) is also invalidated
// here: none of them are keyed by email, so without this a stale response
// cached for whoever was last logged in in this tab could otherwise show
// through for this account too, until its own staleTime happened to expire.
// This also covers what useSessionEventsStream's SSE nudge would eventually
// do anyway: that connection only opens once isAuthenticated flips true (see
// App.tsx), i.e. after this same onSuccess runs, so this tab's own login
// would otherwise miss the very event meant to tell it about itself.
export function useLoginMutation() {
    return useMutation<CurrentUserProfile, Error, LoginRequest>({
        mutationFn: async (payload) => {
            try {
                await loginApi(payload);
                const res = await getCurrentUserApi("useLoginMutation");
                return res.data as CurrentUserProfile;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Login failed"), { cause: error });
            }
        },
        onSuccess: (profile) => {
            useAuthStore.getState().setProfile(profile);
            useAuthStore.getState().setAuthenticated(true);
            queryClient.setQueryData(CURRENT_USER_QUERY_KEY, profile);
            queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY });
            // Prefix match also covers its own children, LAST_LOGIN_QUERY_KEY
            // and MY_LOGIN_TREND_QUERY_KEY, so they don't need a separate call.
            queryClient.invalidateQueries({ queryKey: MY_SECURITY_AUDIT_LOG_QUERY_KEY });
        },
    });
}
