import { useMutation } from "@tanstack/react-query";

import { loginApi, getCurrentUserApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { useAuthStore } from "../../store/authStore";
import { queryClient } from "../../core/queryClient";
import { CURRENT_USER_QUERY_KEY } from "../current_user/useCurrentUserQuery";
import type { CurrentUserProfile } from "../current_user/current_user_types";
import type { LoginRequest } from "./login_types";

// mutationFn logs in, then fetches the fresh profile, so the mutation only
// resolves once the session is fully confirmed. A plain "invalidate and
// hope the query refetches in time" would risk a caller reading
// isAuthenticated before the refetch lands. onSuccess writes straight into
// the Zustand store and the shared query cache so every consumer
// (useAuthStore subscribers and the app-level useCurrentUserQuery) is
// consistent immediately, not after another round trip.
export function useLoginMutation() {
    return useMutation<CurrentUserProfile, Error, LoginRequest>({
        mutationFn: async (payload) => {
            try {
                await loginApi(payload);
                const res = await getCurrentUserApi("useLoginMutation");
                return res.data as CurrentUserProfile;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Login failed"), { cause: error });
            }
        },
        onSuccess: (profile) => {
            useAuthStore.getState().setProfile(profile);
            useAuthStore.getState().setAuthenticated(true);
            queryClient.setQueryData(CURRENT_USER_QUERY_KEY, profile);
        },
    });
}
