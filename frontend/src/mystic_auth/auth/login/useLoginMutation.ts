import { useMutation } from "@tanstack/react-query";
import axios from "axios";

import { loginApi, getCurrentUserApi } from "../../api/auth_api";
import { extractApiErrorMessage, translateErrorCode } from "../../api/apiError";
import { useAuthStore } from "../../store/authStore";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "../../active_sessions/useSessionsQuery";
import { MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY } from "../../audit_log/authorization_log/authorizationLogQueries";
import { MY_SECURITY_AUDIT_LOG_QUERY_KEY } from "../../audit_log/security_log/securityLogQueries";
import { MY_POLICIES_QUERY_KEY } from "../../policies/queries/policyQueries";
import type { CurrentUserProfile } from "../current_user/current_user_types";
import type { LoginRequest } from "./login_types";

// mutationFn logs in, then fetches the fresh profile, so the mutation only resolves
// once the session is fully confirmed (invalidate-and-hope-the-refetch-lands-in-time
// risks a caller reading isAuthenticated too early). onSuccess also invalidates every
// other "me"-scoped query (sessions, policies, audit history): none are keyed by
// email, so without this a stale response cached for the previous account in this tab
// could show through until its own staleTime expired.
export function useLoginMutation() {
    return useMutation<CurrentUserProfile, Error, LoginRequest>({
        mutationFn: async (payload) => {
            try {
                // The app-root session probe may still be resolving the
                // unauthenticated state when a user submits login. Abort that
                // stale request before establishing the new session so its
                // later 401 cannot clear the profile just loaded by this
                // mutation (especially visible on slower mobile browsers).
                await queryClient.cancelQueries({ queryKey: CURRENT_USER_QUERY_KEY });
                await loginApi(payload);
                const res = await getCurrentUserApi("useLoginMutation");
                return res.data as CurrentUserProfile;
            } catch (error) {
                let message = extractApiErrorMessage(error, "Login failed");

                // Preserve a stable, localized recovery message even when a
                // proxy or older backend omits the structured error code.
                if (axios.isAxiosError(error) && !error.response?.data?.code) {
                    if (error.response?.status === 401) {
                        message = translateErrorCode("INVALID_CREDENTIALS") ?? message;
                    } else if (error.response?.status === 429) {
                        message = translateErrorCode("TOO_MANY_ATTEMPTS", { endpoint: "login" }) ?? message;
                    } else if (!error.response) {
                        message = translateErrorCode("NETWORK_ERROR") ?? message;
                    } else if (error.response.status >= 500) {
                        message = translateErrorCode("SERVER_ERROR") ?? message;
                    }
                }

                throw new Error(message, { cause: error });
            }
        },
        onSuccess: (profile) => {
            useAuthStore.getState().setProfile(profile);
            useAuthStore.getState().setAuthenticated(true);
            queryClient.setQueryData(CURRENT_USER_QUERY_KEY, profile);
            queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY });
            // Prefix match also covers its own children, PREVIOUS_LOGIN_QUERY_KEY
            // and MY_LOGIN_TREND_QUERY_KEY, so they don't need a separate call.
            queryClient.invalidateQueries({ queryKey: MY_SECURITY_AUDIT_LOG_QUERY_KEY });
        },
    });
}
