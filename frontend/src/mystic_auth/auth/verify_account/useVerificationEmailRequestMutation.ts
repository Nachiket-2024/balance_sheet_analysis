import { useMutation } from "@tanstack/react-query";

import { verificationEmailRequestApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import type {
    VerificationEmailRequestPayload,
    VerificationEmailRequestResponse,
} from "./verify_account_types";

export function useVerificationEmailRequestMutation() {
    return useMutation<VerificationEmailRequestResponse, Error, VerificationEmailRequestPayload>({
        mutationFn: async (payload) => {
            try {
                const res = await verificationEmailRequestApi(payload);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Verification email request failed"), { cause: error });
            }
        },
    });
}
