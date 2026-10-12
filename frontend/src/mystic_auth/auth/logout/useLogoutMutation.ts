import { useMutation } from "@tanstack/react-query";

import { logoutApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { clearMyAccountSessionCaches } from "../session_lifecycle/clearMyAccountSessionCaches";
import type { LogoutResponse } from "./logout_types";

// clearMyAccountSessionCaches uses setAuthenticated(false), not reset(): reset() sets
// isAuthenticated back to null, which ProtectedRoute reads as "still checking"
// (spinner) rather than "log out now" (redirect).
//
// Runs in onSettled, not onSuccess: POST /auth/logout 400s whenever the refresh_token
// cookie is already gone (expired, or logged out elsewhere), which would skip
// onSuccess and leave the user stuck on a now-401ing page. Clearing local state
// regardless of the backend result matches the backend's own "always clear cookies"
// stance.
export function useLogoutMutation() {
    return useMutation<LogoutResponse, Error, void>({
        mutationFn: async () => {
            try {
                const res = await logoutApi();
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Logout failed"), { cause: error });
            }
        },
        onSettled: clearMyAccountSessionCaches,
    });
}
