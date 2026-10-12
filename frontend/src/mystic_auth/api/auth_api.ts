import api from "./axiosInstance";

export interface SessionRead {
    id: number;
    ip_address: string | null;
    city: string | null;
    country: string | null;
    user_agent: string | null;
    created_at: string;
    last_used_at: string;
    is_current: boolean;
}

export const signupApi = (payload: { name: string; email: string; password: string }) =>
    api.post("/auth/signup", payload);

export const loginApi = (payload: { email: string; password: string }) =>
    api.post("/auth/login", payload);

export const getCurrentUserApi = (src: string = "unknown", signal?: AbortSignal) =>
    api.get("/auth/me", { params: { src }, signal });

export const oauth2LoginGoogleApi = () =>
    api.get("/auth/oauth2/login/google");

export const oauth2CallbackGoogleApi = (code: string) =>
    api.get("/auth/oauth2/callback/google", { params: { code } });

// refresh_token comes from its httponly cookie server-side, nothing to send here.
export const refreshTokenApi = () =>
    api.post("/auth/refresh/");

export const logoutApi = () =>
    api.post("/auth/logout");

export const logoutAllApi = () =>
    api.post("/auth/logout/all");

export const getMySessionsApi = () =>
    api.get<SessionRead[]>("/auth/sessions");

export const revokeSessionApi = (sessionId: number) =>
    api.delete(`/auth/sessions/${sessionId}`);

export const passwordResetRequestApi = (payload: { email: string }) =>
    api.post("/auth/password-reset/request", payload);

export const passwordResetConfirmApi = (payload: { token: string; new_password: string }) =>
    api.post("/auth/password-reset/confirm", payload);

export const verificationEmailRequestApi = (payload: { email: string }) =>
    api.post("/auth/verify-account/request", payload);

// email is for callers' convenience only, not sent: the backend just needs the token.
// Sent as a POST body (not a query param) to keep the token out of browser history and logs.
export const verifyAccountApi = (token: string, _email: string) =>
    api.post("/auth/verify-account", { token });
