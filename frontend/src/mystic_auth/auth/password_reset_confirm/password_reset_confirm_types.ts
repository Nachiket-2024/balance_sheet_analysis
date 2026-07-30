export interface PasswordResetConfirmPayload {
    token: string;
    new_password: string;
}

export interface PasswordResetConfirmResponse {
    message: string;
}
