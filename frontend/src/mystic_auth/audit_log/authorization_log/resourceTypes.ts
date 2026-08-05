/**
 * Mirrors this app's own resource types (see default_policies.py /
 * permissions.py): the fixed set of resources this template's authorization
 * decisions can be scoped to. A downstream project adding its own resource
 * types for its own business domain would extend this list alongside its
 * own new Permission-like values.
 */
export const AUTHORIZATION_RESOURCE_TYPES = ["users", "policies", "security_audit", "*"] as const;
