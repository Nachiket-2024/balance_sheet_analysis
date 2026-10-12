import { useAuthStore } from "../../store/authStore";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "../../active_sessions/useSessionsQuery";
import { MY_POLICIES_QUERY_KEY } from "../../policies/queries/policyQueries";
import { MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY } from "../../audit_log/authorization_log/authorizationLogQueries";
import { MY_SECURITY_AUDIT_LOG_QUERY_KEY } from "../../audit_log/security_log/securityLogQueries";

// Marks the caller signed out and drops every "me"-scoped query. Shared by every
// mutation that ends this browser's session (useLogoutMutation, useLogoutAllMutation,
// useDeleteMyAccountMutation, useConfirmDeleteMyAccountMutation): each reaches this
// same post-logout state from a different API call, so only the cleanup is factored out.
export function clearMyAccountSessionCaches(): void {
    useAuthStore.getState().setAuthenticated(false);
    queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
    // Removed, not just invalidated: none of these queries are keyed by email, so a
    // stale one must never flash for whoever uses this browser next. Prefix match on
    // MY_SECURITY_AUDIT_LOG_QUERY_KEY also covers its children (PREVIOUS_LOGIN_QUERY_KEY,
    // MY_LOGIN_TREND_QUERY_KEY).
    queryClient.removeQueries({ queryKey: SESSIONS_QUERY_KEY });
    queryClient.removeQueries({ queryKey: MY_POLICIES_QUERY_KEY });
    queryClient.removeQueries({ queryKey: MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY });
    queryClient.removeQueries({ queryKey: MY_SECURITY_AUDIT_LOG_QUERY_KEY });
}
