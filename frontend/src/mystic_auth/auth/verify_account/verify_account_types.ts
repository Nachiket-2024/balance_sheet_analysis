export interface VerifyAccountPayload {
    token: string;
    email: string;
}

export interface VerifyAccountResponse {
    message: string;
}

export interface VerificationEmailRequestPayload {
    email: string;
}

export interface VerificationEmailRequestResponse {
    message: string;
}
