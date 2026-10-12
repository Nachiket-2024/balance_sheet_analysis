import { useMutation } from "@tanstack/react-query";

import {
    confirmDeleteMyAccountApi,
    type ConfirmDeleteMyAccountPayload,
    type ConfirmDeleteMyAccountResponse,
} from "../../api/account_settings_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { clearMyAccountSessionCaches } from "../../auth/session_lifecycle/clearMyAccountSessionCaches";

/**
 * useConfirmDeleteMyAccountMutation
 * ----------------------------
 * POST /users/me/confirm-delete: redeems an OAuth-only account's
 * email-confirmation token (see useDeleteMyAccountMutation.ts and
 * docs/mystic_auth/security/decisions-product.md#account-lifecycle-soft-delete-by-default) and performs the
 * deletion. Unauthenticated on the wire, the token is the proof. But if this
 * browser still holds the now-revoked session for the deleted account (the
 * link may be opened on a different device), the same cache cleanup as
 * useDeleteMyAccountMutation's synchronous path still needs to run here, or a
 * stale "logged in" view could flash.
 */
export function useConfirmDeleteMyAccountMutation() {
    return useMutation<ConfirmDeleteMyAccountResponse, Error, ConfirmDeleteMyAccountPayload>({
        mutationFn: async (payload) => {
            try {
                const res = await confirmDeleteMyAccountApi(payload);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Account deletion confirmation failed"), { cause: error });
            }
        },
        onSuccess: clearMyAccountSessionCaches,
    });
}
