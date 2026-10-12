import { useMutation } from "@tanstack/react-query";

import { revokeSessionApi } from "../api/auth_api";
import { extractApiErrorMessage } from "../api/apiError";
import { queryClient } from "../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../auth/current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "./useSessionsQuery";
import translations from "../translations/translations";

/** One session's outcome from a bulk revoke - there's no bulk endpoint for
 * sessions (unlike bulk_assignment_api.ts's policy/permission/role bulk
 * routes), so useBulkRevokeSessionsMutation fans out to the same
 * single-session DELETE this file already wraps, one request per id, and
 * reports each outcome here instead of failing the whole batch on one 404
 * (a session another tab already ended) or 400 (the caller's own current
 * session, which the backend always rejects - see ActiveSessionsCard, which
 * excludes it from selection before this ever runs). */
export interface SessionRevokeResult {
    sessionId: number;
    status: "success" | "error";
    error: string | null;
}

// Deliberately uses invalidateQueries (a background refetch), not
// useLogoutAllMutation/useLogoutMutation's setQueryData(..., null): that
// call is what actually signs this browser out (useAuthStore reads a null
// current-user as logged-out), and revoking a different device's session
// must never do that. Invalidating just refetches GET /auth/me so its
// active_sessions count picks up the change; otherwise the dashboard's
// "Active sessions" stat kept showing the stale pre-revoke count.
export function useRevokeSessionMutation() {
    return useMutation<{ message: string }, Error, number>({
        mutationFn: async (sessionId: number) => {
            try {
                const res = await revokeSessionApi(sessionId);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, translations.t("dashboard:activeSessionsCard.failedEndSession")), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
        },
    });
}

/** Revokes every given session id, best-effort like the real bulk endpoints
 * (bulkAssignmentMutations.ts): one id's 404/400 doesn't stop the rest from
 * going through. Always resolves (never rejects) with one SessionRevokeResult
 * per input id, in input order, so the caller can render a per-item summary
 * the same way BulkOperationResultList does for policy/permission bulk ops. */
export function useBulkRevokeSessionsMutation() {
    return useMutation<SessionRevokeResult[], never, number[]>({
        mutationFn: async (sessionIds: number[]) => {
            const settled = await Promise.allSettled(sessionIds.map((id) => revokeSessionApi(id)));
            return settled.map((outcome, i) => ({
                sessionId: sessionIds[i],
                status: outcome.status === "fulfilled" ? "success" : "error",
                error:
                    outcome.status === "rejected"
                        ? extractApiErrorMessage(outcome.reason, translations.t("dashboard:activeSessionsCard.failedEndSession"))
                        : null,
            }));
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
        },
    });
}
