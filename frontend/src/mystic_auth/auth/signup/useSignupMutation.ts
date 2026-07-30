import { useMutation } from "@tanstack/react-query";

import { signupApi } from "../../api/auth_api";
import { extractApiErrorMessage } from "../../api/apiError";
import type { SignupRequest, SignupResponse } from "./signup_types";

// Signup never touches auth state (the account still needs email
// verification), so this is a plain mutation with no onSuccess side effects.
export function useSignupMutation() {
    return useMutation<SignupResponse, Error, SignupRequest>({
        mutationFn: async (payload) => {
            try {
                const res = await signupApi(payload);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Signup failed"), { cause: error });
            }
        },
    });
}
