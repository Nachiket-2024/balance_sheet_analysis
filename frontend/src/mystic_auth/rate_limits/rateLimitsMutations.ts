import { useMutation } from "@tanstack/react-query";

import { resetRateLimitApi } from "../api/rate_limits_api";
import { extractApiErrorMessage } from "../api/apiError";
import { queryClient } from "../core/queryClient";
import { RATE_LIMITS_QUERY_KEY } from "./rateLimitsQueries";

export function useResetRateLimitMutation() {
    return useMutation<void, Error, string>({
        mutationFn: async (key) => {
            try {
                await resetRateLimitApi(key);
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to reset rate limit"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: RATE_LIMITS_QUERY_KEY });
        },
    });
}
