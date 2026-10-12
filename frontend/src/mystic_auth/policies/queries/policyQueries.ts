import { useQuery } from "@tanstack/react-query";

import {
    listPoliciesApi,
    getPolicyHistoryApi,
    getPolicyHoldersApi,
    getMyPoliciesApi,
    getUserPoliciesApi,
    type ListPoliciesParams,
    type PolicyRead,
} from "../../api/policies_api";
import type { SortDirection } from "../../ui/hooks/useSortState";

export const POLICIES_QUERY_KEY = ["policies"] as const;
export const policyHistoryQueryKey = (policyName: string, page = 1, pageSize = 5) => ["policies", policyName, "history", page, pageSize] as const;
export const policyHoldersQueryKey = (policyName: string) => ["policies", policyName, "holders"] as const;
export const MY_POLICIES_QUERY_KEY = ["policies", "me"] as const;
export const userPoliciesQueryKey = (userEmail: string) => ["policies", "user", userEmail] as const;

// Policies themselves (as opposed to who they're assigned to) change
// rarely, and saving/deleting on PoliciesPage explicitly invalidates this
// key (see policyMutations.ts), so a longer staleTime just avoids
// refetching on unrelated remounts/refocus without risking stale data
// after a real edit.
const POLICIES_STALE_TIME = 5 * 60 * 1000;

/** The full, unfiltered policy list (id-ordered, capped at the backend's
 * default limit=1000), for call sites that want every policy at once
 * rather than one page: UserPoliciesDialog's "assign a policy" dropdown.
 * PoliciesPage itself uses usePoliciesListQuery below, which pages/filters/
 * sorts server-side. */
export function usePoliciesQuery(enabled = true) {
    return useQuery({
        queryKey: POLICIES_QUERY_KEY,
        queryFn: async () => (await listPoliciesApi()).data,
        staleTime: POLICIES_STALE_TIME,
        enabled,
    });
}

export interface PoliciesPage {
    policies: PolicyRead[];
    /** From the X-Total-Count response header; 0 if missing rather than
     * throwing, so a proxy/CORS misconfig degrades to "no pages" instead
     * of crashing. */
    total: number;
}

export interface PoliciesListFilters {
    search?: string;
    resourceType?: string;
    isActive?: boolean;
    containsAction?: string;
    destructiveOnly?: boolean;
    sortBy?: string;
    sortDir?: SortDirection;
}

/** Server-side paged/filtered/sorted policy list, same shape as
 * userQueries.ts's useUsersQuery. queryKey is prefixed with
 * POLICIES_QUERY_KEY (not a separate top-level key) so policyMutations.ts's
 * `invalidateQueries({queryKey: POLICIES_QUERY_KEY})` on create/update/
 * delete invalidates this too, alongside the unpaginated usePoliciesQuery
 * above. */
export function usePoliciesListQuery(
    page: number,
    pageSize: number,
    filters: PoliciesListFilters = {},
    enabled = true
) {
    const params: ListPoliciesParams = { limit: pageSize, offset: (page - 1) * pageSize, ...filters };
    return useQuery<PoliciesPage>({
        queryKey: [...POLICIES_QUERY_KEY, "list", page, pageSize, filters],
        queryFn: async () => {
            const res = await listPoliciesApi(params);
            const total = Number(res.headers["x-total-count"]);
            return { policies: res.data, total: Number.isFinite(total) ? total : 0 };
        },
        // Keeps the current page's rows on screen while a different
        // page/filter/sort loads, same as useUsersQuery.
        enabled,
    });
}

export function usePolicyHistoryQuery(policyName: string, page = 1, pageSize = 5, enabled = true) {
    return useQuery({
        queryKey: policyHistoryQueryKey(policyName, page, pageSize),
        queryFn: async () => {
            const response = await getPolicyHistoryApi(policyName, pageSize, (page - 1) * pageSize);
            const total = Number(response.headers["x-total-count"]);
            return { entries: response.data, total: Number.isFinite(total) ? total : response.data.length };
        },
        placeholderData: (previous) => previous,
        enabled: enabled && !!policyName,
    });
}

/** Every user currently holding this policy: backs the details dialog's
 * "Assigned users" list and (via .length) the delete confirm's holder
 * count. Disabled until the caller actually opens one of those, same
 * lazy-fetch pattern as usePolicyHistoryQuery. */
export function usePolicyHoldersQuery(policyName: string, enabled = true) {
    return useQuery({
        queryKey: policyHoldersQueryKey(policyName),
        queryFn: async () => (await getPolicyHoldersApi(policyName)).data,
        enabled: enabled && !!policyName,
    });
}

export function useMyPoliciesQuery(enabled = true) {
    return useQuery({
        queryKey: MY_POLICIES_QUERY_KEY,
        queryFn: async () => (await getMyPoliciesApi()).data,
        staleTime: POLICIES_STALE_TIME,
        enabled,
    });
}

export function useUserPoliciesQuery(userEmail: string, enabled = true) {
    return useQuery({
        queryKey: userPoliciesQueryKey(userEmail),
        queryFn: async () => (await getUserPoliciesApi(userEmail)).data,
        enabled: enabled && !!userEmail,
    });
}
