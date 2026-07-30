import { useMutation } from "@tanstack/react-query";

import { verifyAccountApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import type { VerifyAccountPayload, VerifyAccountResponse } from "./verify_account_types";

// No auth-state side effects, since a freshly verified account isn't
// automatically logged in.
export function useVerifyAccountMutation() {
    return useMutation<VerifyAccountResponse, Error, VerifyAccountPayload>({
        mutationFn: async (payload) => {
            try {
                const res = await verifyAccountApi(payload.token, payload.email);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Account verification failed"), { cause: error });
            }
        },
    });
}
