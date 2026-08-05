import type { AxiosRequestConfig } from "axios";

import api from "../api/axiosInstance";
import { refreshTokenApi } from "../api/auth_api";

import { useAuthStore } from "../store/authStore";
import { queryClient } from "../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "./current_user/useCurrentUserQuery";
import { SESSIONS_QUERY_KEY } from "../dashboard/manage_sessions/useSessionsQuery";
import { MY_POLICIES_QUERY_KEY } from "../policies/policyQueries";
import { MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY } from "../audit_log/authorization_log/queries";
import { MY_SECURITY_AUDIT_LOG_QUERY_KEY } from "../audit_log/security_log/queries";
import { toaster } from "../ui/toaster/toasterInstance";
import { getPendingSessionRotation } from "./sessionRotationGuard";

// Marks a request as already retried once (post-refresh) so it can't be retried again. Without
// this, a request that still 401s right after a successful refresh (e.g. the refresh rotated the
// session for a *different*, stale reason) would loop forever between "refresh" and "retry".
//
// _retriedAfterRotation is a second, independent one-shot: see the pendingRotation branch below.
// It can't reuse _retriedAfterRefresh, since that flag is what gates entry into this whole block -
// reusing it would make the rotation-wait retry look like a second, disallowed pass instead of one
// extra chance.
interface RetryableRequestConfig extends AxiosRequestConfig {
    _retriedAfterRefresh?: boolean;
    _retriedAfterRotation?: boolean;
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

async function refreshAndRetry(originalRequest: RetryableRequestConfig) {
    await refreshSession();
    originalRequest._retriedAfterRefresh = true;
    return api(originalRequest);
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
                    return await refreshAndRetry(originalRequest);
                } catch {
                    // Refresh itself failed (or, per the block below, failed only because
                    // IT lost the same race). Fall through.
                }
            }

            // Before giving up, check whether a session-rotating request (e.g. the
            // account-settings password change) is still in flight: its account-wide
            // Redis version bump can make even a currently-valid cookie look stale for
            // the brief window before its own response lands with fresh ones (see
            // sessionRotationGuard.ts). Deliberately NOT gated by isEligibleForRefresh -
            // this must also catch POST /auth/refresh's own 401, since that endpoint is
            // excluded from the block above (refreshing a refresh call would otherwise
            // loop) and would otherwise fall straight through to the terminal branch
            // below on the very first lost race, before the retry above ever gets a
            // chance to matter. One extra attempt at the SAME request after the rotation
            // settles (not another refresh - if this request WAS the refresh call, that
            // would just repeat the race) tells a real session death (still 401s) apart
            // from just having lost that race.
            if (originalRequest && !originalRequest._retriedAfterRotation) {
                const pendingRotation = getPendingSessionRotation();
                if (pendingRotation) {
                    originalRequest._retriedAfterRotation = true;
                    await pendingRotation;
                    try {
                        return await api(originalRequest);
                    } catch {
                        // Still failing even after the rotation settled: fall through to
                        // marking the session unauthenticated below, same as any other
                        // genuinely-failed refresh.
                    }
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
            // Only surface this when a real, previously-live session just
            // died (was truly `true`, not the initial `null` every visitor
            // starts at, e.g. someone loading /login directly, whose first
            // GET /auth/me 401 is expected and not an "expiry"). Otherwise
            // a page a user was actively working on (a half-filled form,
            // etc.) silently redirects to /login with no explanation.
            const hadLiveSession = useAuthStore.getState().isAuthenticated === true;

            useAuthStore.getState().setAuthenticated(false);
            queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
            // Removed, not just invalidated, same reasoning as
            // useLogoutMutation's onSuccess: none of these "me"-scoped
            // queries are keyed by email, so a stale one must never flash on
            // screen for whoever logs in next in this browser - including
            // right here, where the session died silently (token expiry),
            // not via an explicit Logout that already handles this.
            queryClient.removeQueries({ queryKey: SESSIONS_QUERY_KEY });
            queryClient.removeQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            queryClient.removeQueries({ queryKey: MY_AUTHORIZATION_AUDIT_LOG_QUERY_KEY });
            queryClient.removeQueries({ queryKey: MY_SECURITY_AUDIT_LOG_QUERY_KEY });

            if (hadLiveSession) {
                // "error" (not "warning"): every other toast in the app is
                // success/error only (see UsersPage, PoliciesPage,
                // ManageSessionsCard, etc.) - "warning"'s orange was the one
                // toast in the app that didn't match either established
                // color, in a theme-aware red/green pair that already works
                // in both light and dark mode.
                toaster.create({
                    title: "Your session has expired",
                    description: "Please log in again to continue.",
                    type: "error",
                });
            }

            return Promise.reject(error);
        }
    );
}
