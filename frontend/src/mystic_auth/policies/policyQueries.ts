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

export function usePoliciesQuery() {
    return useQuery({
        queryKey: POLICIES_QUERY_KEY,
        queryFn: async () => (await listPoliciesApi()).data,
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
    });
}

export function useUserPoliciesQuery(userEmail: string, enabled = true) {
    return useQuery({
        queryKey: userPoliciesQueryKey(userEmail),
        queryFn: async () => (await getUserPoliciesApi(userEmail)).data,
        enabled: enabled && !!userEmail,
    });
}
