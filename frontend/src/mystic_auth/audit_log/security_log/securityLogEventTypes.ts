/**
 * Mirrors backend/mystic_auth/audit_log/audit_log_service.py's event_type
 * constants exactly, the same pattern authorization/permissions.ts already
 * uses for Permission: centralized here so the Security events filter
 * dropdown offers exactly the values the backend actually writes, instead
 * of a typed-in string that can never match a real row.
 */
// "login" (not "login_success"/"login_failure" as two separate options) -
// the Result filter (Success/Failed) already lets you narrow to one or the
// other, so listing both outcomes again here as if they were distinct event
// types was redundant and let you pick a combination that could never match
// anything (event=login_success + Result=Failed). The backend's own
// event_type column still stores "login_success"/"login_failure" as two
// literal values (see audit_log_service.py) - this "login" value is a
// UI-only alias the repository's filter expands back into both
// (audit_log_repository.py's _apply_filters).
export const SECURITY_EVENT_TYPES = [
    "login",
    "logout",
    "logout_all",
    "session_revoked",
    "signup",
    "oauth2_login_success",
    "password_reset_requested",
    "password_reset_confirmed",
    "account_verification_requested",
    "account_verified",
    "account_locked",
    "refresh_token_reuse_detected",
    "account_deleted",
    "account_purged",
    "account_reactivated",
    "policy_assigned",
    "policy_revoked",
    "user_role_changed",
] as const;
