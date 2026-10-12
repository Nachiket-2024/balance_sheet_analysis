/**
 * The fixed set of `endpoint` values a rate-limit key can carry: every
 * `rate_limiter_service.rate_limited("<name>", ...)` call site in
 * auth_routes.py/user_self_service_routes.py, plus "login_lock" (written
 * directly by login_handler.py via login_protection_service, not through
 * the rate_limited decorator). The backend matches `endpoint` exactly, so
 * a free-text filter box couldn't discover valid values; this backs the
 * filter dropdown instead.
 *
 * Keep in sync with the backend's rate_limited(...) call sites if a new
 * rate-limited endpoint is added.
 */
export const RATE_LIMIT_ENDPOINTS = [
    "login",
    "login_lock",
    "signup",
    "oauth2_login",
    "oauth2_callback",
    "get_current_user",
    "logout",
    "logout_all",
    "list_sessions",
    "revoke_session",
    "password_reset_request",
    "password_reset_confirm",
    "verify_account",
    "verify_account_request",
    "account_delete_confirm",
] as const;
