export interface PasswordResetConfirmPayload {
    token: string;
    new_password: string;
}

export interface PasswordResetConfirmResponse {
    message: string;
    // false only when the reset succeeded but the account's other sessions couldn't
    // be confirmed as revoked (Valkey unreachable). See password_reset_service.reset_password.
    sessions_revoked: boolean;
}
