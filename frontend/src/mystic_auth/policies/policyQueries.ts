import { useQuery } from "@tanstack/react-query";

import {
    listPoliciesApi,
    getPolicyHistoryApi,
    getMyPoliciesApi,
    getUserPoliciesApi,
} from "../api/policies_api";

export const POLICIES_QUERY_KEY = ["policies"] as const;
export const policyHistoryQueryKey = (policyName: string) => ["policies", policyName, "history"] as const;
export const MY_POLICIES_QUERY_KEY = ["policies", "me"] as const;
export const userPoliciesQueryKey = (userEmail: string) => ["policies", "user", userEmail] as const;

// Policies themselves (as opposed to who they're assigned to) change rarely
// - an admin editing PoliciesPage explicitly invalidates this key on
// save/delete (see policyMutations.ts), so a longer staleTime here doesn't
// risk showing stale data after an actual edit, it just avoids refetching
// this list on every unrelated remount/refocus.
const POLICIES_STALE_TIME = 5 * 60 * 1000;

export function usePoliciesQuery(enabled = true) {
    return useQuery({
        queryKey: POLICIES_QUERY_KEY,
        queryFn: async () => (await listPoliciesApi()).data,
        staleTime: POLICIES_STALE_TIME,
        enabled,
    });
}

export function usePolicyHistoryQuery(policyName: string, enabled = true) {
    return useQuery({
        queryKey: policyHistoryQueryKey(policyName),
        queryFn: async () => (await getPolicyHistoryApi(policyName)).data,
        enabled: enabled && !!policyName,
    });
}

export function useMyPoliciesQuery() {
    return useQuery({
        queryKey: MY_POLICIES_QUERY_KEY,
        queryFn: async () => (await getMyPoliciesApi()).data,
        staleTime: POLICIES_STALE_TIME,
    });
}

export function useUserPoliciesQuery(userEmail: string, enabled = true) {
    return useQuery({
        queryKey: userPoliciesQueryKey(userEmail),
        queryFn: async () => (await getUserPoliciesApi(userEmail)).data,
        enabled: enabled && !!userEmail,
    });
}
