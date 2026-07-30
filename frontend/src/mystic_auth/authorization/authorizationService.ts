import api from "../api/axiosInstance";

/** One check in a batch-check request/response. */
export interface AuthorizationCheck {
    action: string;
    resourceType: string;
    resource?: Record<string, unknown>;
}

/**
 * One result in a batch-check response, deliberately minimal (see
 * backend/mystic_auth/authorization/schemas/batch_authorization_schema.py): never exposes
 * matched/rejected policies or failed conditions, only enough to drive a UI decision.
 */
export interface AuthorizationCheckResult {
    action: string;
    resource_type: string;
    allowed: boolean;
    denial_reason: string | null;
}

/** A policy as returned by GET /authorization/users/me/policies. */
export interface Policy {
    id: number;
    name: string;
    description: string | null;
    actions: string[];
    resource_type: string;
    conditions: Record<string, unknown> | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
    created_by: string | null;
}

/** GET /authorization/users/me/policies response shape. */
export interface UserPoliciesResponse {
    user_email: string;
    policies: Policy[];
}

/** One entry from GET /authorization/audit-log/me. */
export interface AuditLogEntry {
    id: number;
    user_email: string;
    action: string;
    resource_type: string;
    resource_identifier: string | null;
    allowed: boolean;
    candidate_policy_names: string[];
    granting_policy_names: string[];
    failed_conditions: Record<string, string[]> | null;
    context: Record<string, unknown> | null;
    created_at: string;
}

// This app has no separate single-check endpoint; batch-check with one item IS the
// single-check call: single and batch authorization must produce identical decisions.
export const checkPermission = async (
    action: string,
    resourceType: string,
    resource?: Record<string, unknown>
): Promise<AuthorizationCheckResult> => {
    const res = await api.post("/authorization/batch-check", {
        checks: [{ action, resource_type: resourceType, resource }],
    });
    return res.data.results[0];
};

// checks: 1-50 items per request (see backend's MAX_BATCH_SIZE). Rejects on any HTTP error
// (e.g. an empty or oversized batch, which the backend rejects with 422), same "let the
// caller handle it" contract as checkPermission.
export const checkBatch = async (checks: AuthorizationCheck[]): Promise<AuthorizationCheckResult[]> => {
    const res = await api.post("/authorization/batch-check", {
        checks: checks.map((check) => ({
            action: check.action,
            resource_type: check.resourceType,
            resource: check.resource,
        })),
    });
    return res.data.results;
};

// Self-service: the caller's own policy assignments, no policies:read required.
export const getUserPolicies = async (): Promise<UserPoliciesResponse> => {
    const res = await api.get("/authorization/users/me/policies");
    return res.data;
};

// Self-service: the caller's own authorization decision history, no policies:read required.
export const getAuditLog = async (): Promise<AuditLogEntry[]> => {
    const res = await api.get("/authorization/audit-log/me");
    return res.data;
};
