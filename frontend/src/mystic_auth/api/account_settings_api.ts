import api from "../api/axiosInstance";
import type { ManagedUserRead, UserUpdatePayload } from "../api/users_api";

export const updateMyAccountApi = (payload: UserUpdatePayload) => api.put<ManagedUserRead>("/users/me", payload);

export interface DeleteMyAccountPayload {
    // Omitted for an OAuth-only account (has_password=false), same as changing a password.
    current_password?: string;
}

export interface DeleteMyAccountResponse {
    detail: string;
    // True only for an OAuth-only account: nothing was deleted yet, just a confirmation
    // email sent (see useConfirmDeleteMyAccountMutation.ts for the flow that finishes it).
    confirmation_required?: boolean;
}

// Self-service soft delete, reversible for ACCOUNT_PURGE_GRACE_DAYS (see
// docs/mystic_auth/security/decisions-product.md#account-lifecycle-soft-delete-by-default).
// A password-holding account is deleted immediately. An OAuth-only account instead
// gets a confirmation email and stays untouched until POST /users/me/confirm-delete.
export const deleteMyAccountApi = (payload: DeleteMyAccountPayload) =>
    // axios's `delete` only sends a body via `{ data }`, not a positional arg.
    api.delete<DeleteMyAccountResponse>("/users/me", { data: payload });

export interface ConfirmDeleteMyAccountPayload {
    token: string;
}

export interface ConfirmDeleteMyAccountResponse {
    message: string;
}

// Unauthenticated: the signed, single-use token in the body proves intent,
// same trust model as POST /auth/password-reset/confirm.
export const confirmDeleteMyAccountApi = (payload: ConfirmDeleteMyAccountPayload) =>
    api.post<ConfirmDeleteMyAccountResponse>("/users/me/confirm-delete", payload);
