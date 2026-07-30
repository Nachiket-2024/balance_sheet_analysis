import { useMutation } from "@tanstack/react-query";

import { passwordResetConfirmApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import type {
    PasswordResetConfirmPayload,
    PasswordResetConfirmResponse,
} from "./password_reset_confirm_types";

export function usePasswordResetConfirmMutation() {
    return useMutation<PasswordResetConfirmResponse, Error, PasswordResetConfirmPayload>({
        mutationFn: async (payload) => {
            try {
                const res = await passwordResetConfirmApi(payload);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Password reset confirmation failed"), { cause: error });
            }
        },
    });
}
