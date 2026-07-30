export interface SignupRequest {
    name: string;
    email: string;
    password: string;
}

export interface SignupResponse {
    message: string;
    user_id?: string;
}
