import { useMutation } from "@tanstack/react-query";

import { logoutAllApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { clearMyAccountSessionCaches } from "../session_lifecycle/clearMyAccountSessionCaches";
import type { LogoutResponse } from "../logout/logout_types";

// Same reasoning as useLogoutMutation.ts: setAuthenticated(false) not reset(), and
// cleanup runs in onSettled (not onSuccess) so a 400 on an already-missing
// refresh_token cookie doesn't leave the user stuck on the page.
export function useLogoutAllMutation() {
    return useMutation<LogoutResponse, Error, void>({
        mutationFn: async () => {
            try {
                const res = await logoutAllApi();
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Logout all devices failed"), { cause: error });
            }
        },
        onSettled: clearMyAccountSessionCaches,
    });
}
