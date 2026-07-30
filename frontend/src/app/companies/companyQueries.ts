import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
    createCompanyApi,
    deleteCompanyApi,
    getCompanyApi,
    listCompaniesApi,
    type CompanyCreatePayload,
} from "../api/company_api";

export const COMPANIES_QUERY_KEY = ["companies"] as const;
export const companyQueryKey = (companyId: number) => ["companies", companyId] as const;

export function useCompaniesQuery() {
    return useQuery({
        queryKey: COMPANIES_QUERY_KEY,
        queryFn: async () => (await listCompaniesApi()).data,
    });
}

export function useCompanyQuery(companyId: number, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: companyQueryKey(companyId),
        queryFn: async () => (await getCompanyApi(companyId)).data,
        enabled: options?.enabled,
    });
}

export function useCreateCompanyMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (payload: CompanyCreatePayload) => createCompanyApi(payload),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: COMPANIES_QUERY_KEY }),
    });
}

export function useDeleteCompanyMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (companyId: number) => deleteCompanyApi(companyId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: COMPANIES_QUERY_KEY }),
    });
}
