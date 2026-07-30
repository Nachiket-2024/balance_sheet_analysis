import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { getCurrentUserApi } from "../../api/auth_api";
import { useAuthStore } from "../../store/authStore";
import type { CurrentUserProfile } from "./current_user_types";

// Shared across this hook, every mutation hook that needs to invalidate/
// refresh the session, and setupAuthInterceptor.ts, keep them all
// referencing this constant rather than repeating the literal array.
export const CURRENT_USER_QUERY_KEY = ["currentUser"] as const;

/**
 * Fetches GET /auth/me. A 401 (no valid session) is the normal, expected
 * "logged out" outcome, not a retryable failure: retry is disabled
 * app-wide on the shared queryClient (see core/queryClient.ts).
 */
export function useCurrentUserQuery() {
    return useQuery({
        queryKey: CURRENT_USER_QUERY_KEY,
        queryFn: async () => {
            const res = await getCurrentUserApi("useCurrentUserQuery");
            return res.data as CurrentUserProfile;
        },
    });
}

/**
 * Runs the current-user query and mirrors its result into the Zustand auth
 * store. Call this ONCE, at the app root (see App.tsx): every other
 * component reads auth state from useAuthStore, not from this hook directly,
 * so a second call here would just be a redundant subscription to the same
 * query cache entry.
 */
export function useAuthSession(): void {
    const { data, isSuccess, isError } = useCurrentUserQuery();
    const setProfile = useAuthStore((s) => s.setProfile);
    const setAuthenticated = useAuthStore((s) => s.setAuthenticated);
    const clearProfile = useAuthStore((s) => s.clearProfile);

    useEffect(() => {
        if (isSuccess && data) {
            setProfile(data);
            setAuthenticated(true);
        } else if (isError) {
            clearProfile();
            setAuthenticated(false);
        }
    }, [isSuccess, isError, data, setProfile, setAuthenticated, clearProfile]);
}
