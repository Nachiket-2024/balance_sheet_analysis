import { useEffect } from "react";

import settings from "../../core/settings";
import { queryClient } from "../../core/queryClient";
import { useAuthStore } from "../../store/authStore";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "../../active_sessions/useSessionsQuery";
import { PREVIOUS_LOGIN_QUERY_KEY } from "../../dashboard/usePreviousLoginQuery";
import { wasSelfPermissionMutationRecent } from "./selfPermissionMutationGuard";

// Opens an SSE (Server-Sent Events: a one-way, auto-reconnecting push channel from
// server to browser) connection to GET /auth/session-events while authenticated, so
// this tab learns instantly when a session is revoked/created or this account's
// policies change elsewhere, instead of waiting on the next background poll.
//
// Reacts by invalidating queries, not by trusting the event payload: the event is
// just a "something changed, go recheck" nudge; only the resulting GET /auth/me is
// authoritative. This channel is shared by every session on the account, so a
// sibling session's revoke must never log this one out by itself.
//
// Call this once, at the app root (see App.tsx), same as useAuthSession.
export function useSessionEventsStream(): void {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    useEffect(() => {
        if (!isAuthenticated) return;

        const source = new EventSource(`${settings.apiBaseUrl}/auth/session-events`, {
            withCredentials: true,
        });

        source.onmessage = (event) => {
            let type: string | undefined;
            try {
                type = (JSON.parse(event.data) as { type?: string }).type;
            } catch {
                // Malformed payload: fall through to default handling instead of
                // losing the nudge entirely.
            }

            if (type === "permissions_changed") {
                // Fail closed synchronously, before any network round-trip:
                // ProtectedRoute/IfCan/the sidebar read permissions reactively from
                // the store, so zeroing it here instantly redirects a now-forbidden
                // route and hides now-forbidden actions without waiting on GET
                // /auth/me (pages using keepPreviousData would otherwise flash stale
                // data before their 403 landed).
                //
                // Skipped if this tab caused the change itself (e.g. a caller
                // granting themselves a permission): it already knows the true
                // outcome from its own mutation response, so zeroing here would read
                // as a live revoke and bounce it before resetQueries() below restores
                // the real list. See selfPermissionMutationGuard.ts.
                if (!wasSelfPermissionMutationRecent()) {
                    useAuthStore.getState().dropPermissions();
                }

                // resetQueries (not invalidateQueries) drops cached data outright, so
                // an unaffected page has nothing stale left to serve as a
                // keepPreviousData placeholder either.
                queryClient.resetQueries();
                return;
            }

            queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: PREVIOUS_LOGIN_QUERY_KEY });
        };

        // EventSource auto-reconnects with browser-native backoff, so
        // errors pass silently rather than surfacing every transient blip.
        source.onerror = () => {};

        return () => source.close();
    }, [isAuthenticated]);
}
