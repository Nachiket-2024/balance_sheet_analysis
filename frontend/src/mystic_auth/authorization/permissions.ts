/**
 * Mirrors backend/mystic_auth/authorization/permissions.py's Permission enum exactly.
 * Centralized so ProtectedRoute/IfCan/Authorized reference a constant instead of retyping
 * the raw string: a typo in a literal string silently denies access, with no compiler error.
 */
export const PERMISSIONS = {
    USERS_READ_OWN: "users:read_own",
    USERS_UPDATE_OWN: "users:update_own",
    USERS_LIST_ALL: "users:list_all",
    USERS_UPDATE_ANY: "users:update_any",
    USERS_DEACTIVATE_ANY: "users:deactivate_any",
    USERS_ASSIGN_ROLE: "users:assign_role",
    USERS_ASSIGN_SYSTEM_ROLE: "users:assign_system_role",
    USERS_DELETE_ANY: "users:delete_any",
    USERS_REACTIVATE: "users:reactivate",
    POLICIES_READ: "policies:read",
    POLICIES_CREATE: "policies:create",
    POLICIES_UPDATE: "policies:update",
    POLICIES_DELETE: "policies:delete",
    POLICIES_ASSIGN: "policies:assign",
    POLICIES_REVOKE: "policies:revoke",
    PERMISSIONS_GRANT: "permissions:grant",
    PERMISSIONS_REVOKE: "permissions:revoke",
    PERMISSIONS_READ: "permissions:read",
    SECURITY_AUDIT_READ: "security_audit:read",
    RATE_LIMITS_READ: "rate_limits:read",
    RATE_LIMITS_RESET: "rate_limits:reset",
} as const;

export type PermissionValue = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];
