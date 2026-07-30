/**
 * Mirrors backend/mystic_auth/authorization/permissions.py's Permission enum values
 * exactly. Centralized here so every ProtectedRoute/IfCan/Authorized call
 * site references a constant instead of retyping the raw string: a typo in
 * a literal string silently fails closed (denies access) with no compiler
 * error, which is easy to miss in review.
 */
export const PERMISSIONS = {
    USERS_READ_OWN: "users:read_own",
    USERS_UPDATE_OWN: "users:update_own",
    USERS_LIST_ALL: "users:list_all",
    USERS_UPDATE_ANY: "users:update_any",
    USERS_DELETE_ANY: "users:delete_any",
    USERS_ASSIGN_ROLE: "users:assign_role",
    USERS_ASSIGN_SYSTEM_ROLE: "users:assign_system_role",
    USERS_PURGE: "users:purge",
    USERS_REACTIVATE: "users:reactivate",
    POLICIES_READ: "policies:read",
    POLICIES_CREATE: "policies:create",
    POLICIES_UPDATE: "policies:update",
    POLICIES_DELETE: "policies:delete",
    POLICIES_ASSIGN: "policies:assign",
    POLICIES_REVOKE: "policies:revoke",
    SECURITY_AUDIT_READ: "security_audit:read",
} as const;

export type PermissionValue = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];
