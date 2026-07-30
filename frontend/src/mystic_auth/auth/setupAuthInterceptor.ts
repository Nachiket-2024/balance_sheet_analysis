import type { AxiosRequestConfig } from "axios";

import api from "../api/axiosInstance";
import { refreshTokenApi } from "../api/auth_api";

import { useAuthStore } from "../store/authStore";
import { queryClient } from "../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "./current_user/useCurrentUserQuery";

// Marks a request as already retried once (post-refresh) so it can't be retried again. Without
// this, a request that still 401s right after a successful refresh (e.g. the refresh rotated the
// session for a *different*, stale reason) would loop forever between "refresh" and "retry".
interface RetryableRequestConfig extends AxiosRequestConfig {
    _retriedAfterRefresh?: boolean;
}

// Auth endpoints deliberately excluded from the silent-refresh-and-retry path below. A 401 from
// these means something other than "my access token expired mid-session": login/signup 401 on
// wrong credentials (there's no session to refresh at all), refresh's own 401 (refreshing a
// refresh call would loop forever), and logout/password-reset/verify/oauth2 flows that were
// never carrying a still-valid session to begin with.
const AUTH_ENDPOINTS_EXCLUDED_FROM_REFRESH = [
    "/auth/login",
    "/auth/signup",
    "/auth/refresh",
    "/auth/logout",
    "/auth/password-reset",
    "/auth/verify-account",
    "/auth/oauth2",
];

// Single-flight refresh coordination: if several requests 401 at once (e.g. a page fires
// multiple API calls in parallel right as the access token expires), they must all await the
// SAME in-flight refresh call rather than each independently POSTing /auth/refresh/, since the
// backend already treats refresh tokens as single-use-then-rotated, so a second concurrent
// refresh call would find the first one's token already rotated out from under it and fail as
// if it were a replay.
let refreshInFlight: Promise<void> | null = null;

function refreshSession(): Promise<void> {
    if (!refreshInFlight) {
        refreshInFlight = refreshTokenApi()
            .then(() => undefined)
            .finally(() => {
                refreshInFlight = null;
            });
    }
    return refreshInFlight;
}

/**
 * Registers a response interceptor on the shared `api` instance that, on a 401 from an endpoint
 * eligible for silent refresh, attempts to rotate the session via /auth/refresh/ and retry the
 * original request exactly once. If refresh fails, the endpoint isn't eligible, or this is
 * already a post-refresh retry that 401'd again, marks the Zustand auth store as unauthenticated
 * and invalidates the cached currentUser query: every ProtectedRoute-wrapped page already
 * re-renders reactively off that store and redirects to /login, so no hard `window.location`
 * redirect is needed here.
 *
 * Deliberately 401-only, not 401-or-403: a 403 means the caller IS authenticated but lacks a
 * specific permission, so forcing a logout/redirect-to-login on that would be confusing (the
 * session is fine) and would fight with the conditional-rendering/route-guard components
 * (Authorized/IfCan/ProtectedRoute) that are meant to handle "you don't have this permission"
 * without ending the session. Only a 401 means the session itself is no longer valid (or, per
 * this fix, might still be salvageable via one refresh attempt).
 *
 * Lives in its own module (rather than inside axiosInstance.ts itself) specifically to avoid a
 * circular import: axiosInstance.ts -> queryClient.ts -> useCurrentUserQuery.ts -> auth_api.ts ->
 * axiosInstance.ts. Keeping the core/queryClient imports out of axiosInstance.ts breaks that
 * cycle. Call once at app startup (see main.tsx), after `api` exists.
 */
export function setupAuthInterceptor(): void {
    api.interceptors.response.use(
        (response) => response,
        async (error) => {
            if (error?.response?.status !== 401) {
                return Promise.reject(error);
            }

            const originalRequest = error.config as RetryableRequestConfig | undefined;
            const requestUrl = originalRequest?.url ?? "";
            const isEligibleForRefresh = !AUTH_ENDPOINTS_EXCLUDED_FROM_REFRESH.some((path) =>
                requestUrl.includes(path)
            );

            if (isEligibleForRefresh && originalRequest && !originalRequest._retriedAfterRefresh) {
                try {
                    await refreshSession();
                    originalRequest._retriedAfterRefresh = true;
                    return api(originalRequest);
                } catch {
                    // Refresh itself failed. Fall through to marking the session unauthenticated.
                }
            }

            // Not eligible, or refresh/retry failed: the session is genuinely over. Use
            // setQueryData(null), NOT invalidateQueries: invalidating a still-mounted/active
            // query (useAuthSession keeps this one mounted for the app's whole lifetime)
            // triggers TanStack Query's automatic refetch of that query, which would
            // immediately re-request GET /auth/me, 401 again, land back in this exact branch,
            // invalidate again, and so on forever. setQueryData writes the "logged out" result
            // directly into the cache without provoking another fetch, the same pattern
            // useLogoutMutation's onSuccess already uses.
            useAuthStore.getState().setAuthenticated(false);
            queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);

            return Promise.reject(error);
        }
    );
}
