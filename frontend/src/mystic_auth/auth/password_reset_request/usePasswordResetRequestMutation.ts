import { useMutation } from "@tanstack/react-query";

import { passwordResetRequestApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import type {
    PasswordResetRequestPayload,
    PasswordResetRequestResponse,
} from "./password_reset_request_types";

export function usePasswordResetRequestMutation() {
    return useMutation<PasswordResetRequestResponse, Error, PasswordResetRequestPayload>({
        mutationFn: async (payload) => {
            try {
                const res = await passwordResetRequestApi(payload);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Password reset request failed"), { cause: error });
            }
        },
    });
}
