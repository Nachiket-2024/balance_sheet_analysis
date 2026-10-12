import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getCurrentUserApi } from "../../api/auth_api";
import { useAuthStore } from "../../store/authStore";
import { useAppearanceStore } from "../../store/appearanceStore";
import type { CurrentUserProfile } from "./current_user_types";

// Shared by this hook, every mutation hook that invalidates/refreshes the session, and
// setupAuthInterceptor.ts, so they all reference one constant instead of the literal array.
export const CURRENT_USER_QUERY_KEY = ["currentUser"] as const;

// This query is mounted once at the app root and never remounts on navigation, so a
// tab with everything cached could show "signed in" for a while after being revoked
// elsewhere, with no request to surface the resulting 401. useSessionEventsStream.ts
// (SSE) is the primary way a tab notices within milliseconds; this poll is just the
// fallback for a silently dropped connection, so 2 minutes is fine.
const REVALIDATE_INTERVAL_MS = 2 * 60 * 1000;

// Fetches GET /auth/me. A 401 (no valid session) is the normal "logged out" outcome,
// not a retryable failure; retry is disabled app-wide on the shared queryClient.
export function useCurrentUserQuery() {
    return useQuery({
        queryKey: CURRENT_USER_QUERY_KEY,
        queryFn: async ({ signal }) => {
            const res = await getCurrentUserApi("useCurrentUserQuery", signal);
            return res.data as CurrentUserProfile;
        },
        // This is specifically the query that needs to notice a revocation even in a
        // backgrounded tab, so it keeps polling there too.
        refetchInterval: REVALIDATE_INTERVAL_MS,
        refetchIntervalInBackground: true,
    });
}

// Runs the current-user query and mirrors its result into the Zustand auth store.
// Call this ONCE, at the app root (see App.tsx): every other component reads auth
// state from useAuthStore, so a second call here would just duplicate the subscription.
export function useAuthSession(): void {
    const { data, isSuccess, isError } = useCurrentUserQuery();
    const queryClient = useQueryClient();
    const setProfile = useAuthStore((s) => s.setProfile);
    const setAuthenticated = useAuthStore((s) => s.setAuthenticated);
    const clearProfile = useAuthStore((s) => s.clearProfile);

    useEffect(() => {
        if (isSuccess && data) {
            setProfile(data);
            setAuthenticated(true);
            // Server value wins once known, overriding appearanceStore's localStorage-cached
            // guess from module load (e.g. colors picked on another device).
            const appearance = useAppearanceStore.getState();
            appearance.setBrandColor(data.brand_color ?? null);
        } else if (isError && queryClient.getQueryState(CURRENT_USER_QUERY_KEY)?.status === "error") {
            const authenticatedAt = useAuthStore.getState().authenticatedAt;
            const errorUpdatedAt = queryClient.getQueryState(CURRENT_USER_QUERY_KEY)?.errorUpdatedAt ?? 0;
            if (authenticatedAt !== null && errorUpdatedAt < authenticatedAt) return;
            clearProfile();
            setAuthenticated(false);
            const appearance = useAppearanceStore.getState();
            appearance.setBrandColor(null);
        }
    }, [isSuccess, isError, data, queryClient, setProfile, setAuthenticated, clearProfile]);
}
