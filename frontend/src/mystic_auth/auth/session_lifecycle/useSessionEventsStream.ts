import { useEffect } from "react";

import settings from "../../core/settings";
import { queryClient } from "../../core/queryClient";
import { useAuthStore } from "../../store/authStore";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "../../dashboard/manage_sessions/useSessionsQuery";
import { LAST_LOGIN_QUERY_KEY } from "../../dashboard/useLastLoginQuery";

/**
 * Opens a Server-Sent Events connection to GET /auth/session-events while
 * authenticated, so this tab finds out the instant its session (or a
 * sibling session on the same account) is revoked OR created elsewhere -
 * logout-all, a password change, a targeted Manage Sessions revoke,
 * reuse-detection, a fresh login from another device/tab - instead of
 * waiting on its next background poll (useCurrentUserQuery's and
 * useSessionsQuery's own refetchInterval, kept as a fallback for the rare
 * case this connection silently drops without the browser's native auto-
 * reconnect noticing) or a window-focus refetch.
 *
 * Deliberately reacts by invalidating the existing queries, not by acting
 * on the event's own payload: the event is just a "something changed, go
 * check now" nudge (see backend's user_session/session_events.py), never an
 * authoritative "you are logged out" on its own - only the resulting GET
 * /auth/me actually decides that. This channel is shared by every session
 * on the account, so a sibling session's revoke must never log this one out
 * by itself; it only earns the right to re-check.
 *
 * Call this once, at the app root (see App.tsx), same as useAuthSession.
 */
export function useSessionEventsStream(): void {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    useEffect(() => {
        if (!isAuthenticated) return;

        const source = new EventSource(`${settings.apiBaseUrl}/auth/session-events`, {
            withCredentials: true,
        });

        source.onmessage = () => {
            queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: LAST_LOGIN_QUERY_KEY });
        };

        // EventSource retries on its own (browser-native exponential
        // backoff) after a dropped connection - nothing to do here beyond
        // letting errors pass silently rather than surfacing every
        // transient network blip as a user-facing error. The 30s poll
        // fallback covers the gap while a reconnect is in progress.
        source.onerror = () => {};

        return () => source.close();
    }, [isAuthenticated]);
}
