import api from "./axiosInstance";

export const signupApi = (payload: { name: string; email: string; password: string }) =>
    api.post("/auth/signup", payload);

export const loginApi = (payload: { email: string; password: string }) =>
    api.post("/auth/login", payload);

export const getCurrentUserApi = (src: string = "unknown") =>
    api.get("/auth/me", { params: { src } });

export const oauth2LoginGoogleApi = () =>
    api.get("/auth/oauth2/login/google");

export const oauth2CallbackGoogleApi = (code: string) =>
    api.get("/auth/oauth2/callback/google", { params: { code } });

// refresh_token is read from its httponly cookie server-side, so nothing is sent explicitly here.
export const refreshTokenApi = () =>
    api.post("/auth/refresh/");

export const logoutApi = () =>
    api.post("/auth/logout");

export const logoutAllApi = () =>
    api.post("/auth/logout/all");

export const passwordResetRequestApi = (payload: { email: string }) =>
    api.post("/auth/password-reset/request", payload);

export const passwordResetConfirmApi = (payload: { token: string; new_password: string }) =>
    api.post("/auth/password-reset/confirm", payload);

export const verificationEmailRequestApi = (payload: { email: string }) =>
    api.post("/auth/verify-account/request", payload);

// email is accepted for callers' convenience but not sent: the backend only needs the token.
// Sent as a POST body rather than a GET query param to avoid exposing the token in browser
// history, server access logs, and Referer headers.
export const verifyAccountApi = (token: string, _email: string) =>
    api.post("/auth/verify-account", { token });
