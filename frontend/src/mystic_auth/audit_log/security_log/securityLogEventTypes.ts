/**
 * Mirrors backend/mystic_auth/audit_log/audit_log_service.py's event_type constants exactly,
 * same pattern as authorization/permissions.ts's Permission: keeps the filter dropdown
 * offering only values the backend actually writes.
 */
// "login", not "login_success"/"login_failure" as two options: the Result filter (Success/
// Failed) already narrows to one, so two event options would allow an impossible combination
// (event=login_success + Result=Failed). The backend still stores both literal values;
// "login" is a UI-only alias that audit_log_repository.py's _apply_filters expands back.
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
    "policy_action_revoked",
    "permission_granted",
    "permission_revoked",
    "user_role_changed",
] as const;

export function humanizeSecurityEventType(value: string): string {
    const label = value.replace(/[_-]+/g, " ").trim();
    return label ? label.charAt(0).toUpperCase() + label.slice(1) : value;
}

/**
 * Groups SECURITY_EVENT_TYPES for the Event picker (GroupedSearchSelect in SecurityFilterBar),
 * the same "Sign-in / Sessions / Account / Password / Access changes" split
 * .project/audit-log-design-review.md called for. Order here is the order groups render in.
 */
export const SECURITY_EVENT_TYPE_GROUPS: Record<string, readonly (typeof SECURITY_EVENT_TYPES)[number][]> = {
    signIn: ["login", "oauth2_login_success", "refresh_token_reuse_detected"],
    sessions: ["logout", "logout_all", "session_revoked"],
    account: ["signup", "account_verification_requested", "account_verified", "account_locked", "account_deleted", "account_purged", "account_reactivated"],
    password: ["password_reset_requested", "password_reset_confirmed"],
    accessChanges: ["policy_assigned", "policy_revoked", "policy_action_revoked", "permission_granted", "permission_revoked", "user_role_changed"],
};
