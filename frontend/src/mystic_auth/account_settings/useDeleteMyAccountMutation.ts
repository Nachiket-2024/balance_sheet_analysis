import { useMutation } from "@tanstack/react-query";

import {
    deleteMyAccountApi,
    type DeleteMyAccountPayload,
    type DeleteMyAccountResponse,
} from "../api/account_settings_api";
import { extractApiErrorMessage } from "../api/apiError";
import { clearMyAccountSessionCaches } from "../auth/session_lifecycle/clearMyAccountSessionCaches";

/**
 * useDeleteMyAccountMutation
 * ----------------------------
 * DELETE /users/me. For a password-holding account this soft-deletes the
 * caller's account immediately (revoked sessions, recoverable by a permission holder
 * for ACCOUNT_PURGE_GRACE_DAYS, then permanently purged, see
 * DeleteAccountCard.tsx's copy and docs/mystic_auth/security/decisions.md).
 * The route already revokes every session including this one, so on success
 * this mirrors useLogoutMutation's cache cleanup: mark unauthenticated
 * immediately rather than waiting on a currentUser refetch that would 401 by
 * design, and drop every "me"-scoped query so nothing stale flashes for
 * whoever uses this browser next.
 *
 * For an OAuth-only account (no password to re-confirm with), the response
 * instead carries `confirmation_required: true`: nothing was deleted yet,
 * only a confirmation email was sent, so the session and its caches stay as
 * they were. DeleteAccountCard.tsx branches on that flag to show "check your
 * email" messaging instead of navigating away.
 */
export function useDeleteMyAccountMutation() {
    return useMutation<DeleteMyAccountResponse, Error, DeleteMyAccountPayload>({
        mutationFn: async (payload) => {
            try {
                const res = await deleteMyAccountApi(payload);
                return res.data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to delete account"), { cause: error });
            }
        },
        onSuccess: (data) => {
            if (data.confirmation_required) {
                return;
            }

            clearMyAccountSessionCaches();
        },
    });
}
