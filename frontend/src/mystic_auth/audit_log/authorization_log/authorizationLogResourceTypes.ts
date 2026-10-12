/**
 * Mirrors this app's own resource types (see default_policies.py / permissions.py): the fixed
 * set of resources authorization decisions can be scoped to. A downstream project adding its
 * own resource types would extend this list alongside its own Permission-like values.
 */
export const AUTHORIZATION_RESOURCE_TYPES = [
    "users",
    "policies",
    "permissions",
    "security_audit",
    "rate_limits",
    "*",
] as const;
