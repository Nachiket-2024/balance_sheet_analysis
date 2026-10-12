import { useMutation } from "@tanstack/react-query";

import {
    bulkAssignPoliciesApi,
    bulkRemovePoliciesApi,
    bulkAssignPermissionsApi,
    bulkRemovePermissionsApi,
    bulkUpdateRoleApi,
    type BulkResponse,
} from "../../api/bulk_assignment_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { queryClient } from "../../core/queryClient";
import { useAuthStore } from "../../store/authStore";
import { CURRENT_USER_QUERY_KEY } from "../../auth/current_user/useCurrentUserQuery";
import { markSelfPermissionMutation } from "../../auth/session_lifecycle/selfPermissionMutationGuard";
import { MY_POLICIES_QUERY_KEY, userPoliciesQueryKey } from "./policyQueries";
import { MY_PERMISSIONS_QUERY_KEY, PERMISSION_CATALOG_USAGE_QUERY_KEY, userPermissionsQueryKey } from "./permissionQueries";
import { USERS_QUERY_KEY } from "../../users/queries/userQueries";

/** A bulk response fans out across many users, so there's no single query
 * key to invalidate like the single-item mutations do. Each mutation below
 * invalidates once per distinct user_email actually present in the
 * response, not the request, since an item that errored before reaching
 * the database shouldn't trigger a refetch for an unchanged user. */
function distinctEmails(data: BulkResponse): string[] {
    return [...new Set(data.results.map((r) => r.user_email))];
}

/**
 * `marksPermissionChange` also arms selfPermissionMutationGuard, so this
 * tab's own "permissions_changed" SSE echo (see useSessionEventsStream.ts)
 * isn't read as a live revoke before the invalidation above resolves. Only
 * pass it for a bulk mutation that can actually emit that event for the
 * caller themselves - not the role mutation below, whose targets can never
 * include the caller (the backend rejects a self-targeted role change).
 */
function invalidateSelfIfIncluded(emails: string[], options?: { marksPermissionChange?: boolean }) {
    if (!emails.includes(useAuthStore.getState().email ?? "")) return;
    queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
    if (options?.marksPermissionChange) {
        markSelfPermissionMutation();
    }
}

function wrapError(action: string) {
    return (error: unknown) => {
        throw new Error(extractApiErrorMessage(error, action), { cause: error });
    };
}

// Mirrors backend/.../bulk_schema.py's _MAX_BULK_ITEMS: each bulk endpoint
// rejects a request with more than 200 items, so "select all matching
// filters" (which can select far more than that) has to split into several
// requests instead of one.
const BULK_REQUEST_CHUNK_SIZE = 200;

function chunk<T>(items: T[], size: number): T[][] {
    const chunks: T[][] = [];
    for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size));
    return chunks;
}

/** Runs a bulk API call over `userEmails` in <=200-item requests, in
 * sequence (not parallel: keeps worst-case DB load the same shape the
 * backend already assumes one request has), merging every chunk's
 * BulkResponse into one so callers never need to know chunking happened. */
async function runChunkedBulk(
    userEmails: string[],
    call: (chunkEmails: string[]) => Promise<{ data: BulkResponse }>
): Promise<BulkResponse> {
    const merged: BulkResponse = { results: [], success_count: 0, error_count: 0 };
    for (const emailChunk of chunk(userEmails, BULK_REQUEST_CHUNK_SIZE)) {
        const { data } = await call(emailChunk);
        merged.results.push(...data.results);
        merged.success_count += data.success_count;
        merged.error_count += data.error_count;
    }
    return merged;
}

export function useBulkAssignPoliciesMutation() {
    return useMutation<BulkResponse, Error, { userEmails: string[]; policyName?: string; policyNames?: string[] }>({
        mutationFn: async ({ userEmails, policyName, policyNames }) => {
            try {
                const merged: BulkResponse = { results: [], success_count: 0, error_count: 0 };
                for (const name of policyNames ?? (policyName ? [policyName] : [])) {
                    const result = await runChunkedBulk(userEmails, (emails) => bulkAssignPoliciesApi(emails, name));
                    merged.results.push(...result.results); merged.success_count += result.success_count; merged.error_count += result.error_count;
                }
                return merged;
            } catch (error) {
                return wrapError("Failed to bulk-assign policy")(error);
            }
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            const emails = distinctEmails(data);
            emails.forEach((email) => queryClient.invalidateQueries({ queryKey: userPoliciesQueryKey(email) }));
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            invalidateSelfIfIncluded(emails, { marksPermissionChange: true });
        },
    });
}

export function useBulkRemovePoliciesMutation() {
    return useMutation<BulkResponse, Error, { userEmails: string[]; policyName?: string; policyNames?: string[] }>({
        mutationFn: async ({ userEmails, policyName, policyNames }) => {
            try {
                const merged: BulkResponse = { results: [], success_count: 0, error_count: 0 };
                for (const name of policyNames ?? (policyName ? [policyName] : [])) {
                    const result = await runChunkedBulk(userEmails, (emails) => bulkRemovePoliciesApi(emails, name));
                    merged.results.push(...result.results); merged.success_count += result.success_count; merged.error_count += result.error_count;
                }
                return merged;
            } catch (error) {
                return wrapError("Failed to bulk-remove policy")(error);
            }
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            const emails = distinctEmails(data);
            emails.forEach((email) => queryClient.invalidateQueries({ queryKey: userPoliciesQueryKey(email) }));
            queryClient.invalidateQueries({ queryKey: MY_POLICIES_QUERY_KEY });
            invalidateSelfIfIncluded(emails, { marksPermissionChange: true });
        },
    });
}

export function useBulkAssignPermissionsMutation() {
    return useMutation<
        BulkResponse,
        Error,
        { userEmails: string[]; action?: string; actions?: { action: string; resourceType: string }[]; resourceType?: string; conditions?: Record<string, unknown> }
    >({
        mutationFn: async ({ userEmails, action, actions, resourceType, conditions }) => {
            try {
                const selected = actions ?? (action && resourceType ? [{ action, resourceType }] : []);
                const merged: BulkResponse = { results: [], success_count: 0, error_count: 0 };
                for (const item of selected) {
                    const result = await runChunkedBulk(userEmails, (emails) => bulkAssignPermissionsApi(emails, item.action, item.resourceType, conditions));
                    merged.results.push(...result.results); merged.success_count += result.success_count; merged.error_count += result.error_count;
                }
                return merged;
            } catch (error) {
                return wrapError("Failed to bulk-grant permission")(error);
            }
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            const emails = distinctEmails(data);
            emails.forEach((email) => queryClient.invalidateQueries({ queryKey: userPermissionsQueryKey(email) }));
            queryClient.invalidateQueries({ queryKey: MY_PERMISSIONS_QUERY_KEY });
            invalidateSelfIfIncluded(emails, { marksPermissionChange: true });
        },
    });
}

export function useBulkRemovePermissionsMutation() {
    return useMutation<BulkResponse, Error, { userEmails: string[]; action?: string; actions?: { action: string; resourceType: string }[]; resourceType?: string }>({
        mutationFn: async ({ userEmails, action, actions, resourceType }) => {
            try {
                const selected = actions ?? (action && resourceType ? [{ action, resourceType }] : []);
                const merged: BulkResponse = { results: [], success_count: 0, error_count: 0 };
                for (const item of selected) {
                    const result = await runChunkedBulk(userEmails, (emails) => bulkRemovePermissionsApi(emails, item.action, item.resourceType));
                    merged.results.push(...result.results); merged.success_count += result.success_count; merged.error_count += result.error_count;
                }
                return merged;
            } catch (error) {
                return wrapError("Failed to bulk-revoke permission")(error);
            }
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY });
            const emails = distinctEmails(data);
            emails.forEach((email) => queryClient.invalidateQueries({ queryKey: userPermissionsQueryKey(email) }));
            queryClient.invalidateQueries({ queryKey: MY_PERMISSIONS_QUERY_KEY });
            invalidateSelfIfIncluded(emails, { marksPermissionChange: true });
        },
    });
}

export function useBulkUpdateRoleMutation() {
    return useMutation<BulkResponse, Error, { userEmails: string[]; role: string }>({
        mutationFn: async ({ userEmails, role }) => {
            try {
                return await runChunkedBulk(userEmails, (emails) => bulkUpdateRoleApi(emails, role));
            } catch (error) {
                return wrapError("Failed to bulk-update role")(error);
            }
        },
        onSuccess: (data) => {
            const emails = distinctEmails(data);
            // Unlike the policy/permission mutations above, the users table
            // itself renders the role column, not a separate per-user
            // dialog, so the list query needs invalidating too.
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
            invalidateSelfIfIncluded(emails);
        },
    });
}
