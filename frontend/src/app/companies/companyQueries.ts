import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
    createCompanyApi,
    deleteCompanyApi,
    getCompanyApi,
    getCompanyStatsApi,
    listCompaniesApi,
    searchCompanyTickersApi,
    updateCompanyApi,
    type CompanyCreatePayload,
    type CompanyListItem,
    type CompanyUpdatePayload,
} from "../api/company_api";
import type { SortDirection } from "../app_sdk";

export const COMPANIES_QUERY_KEY = ["companies"] as const;
export const COMPANY_STATS_QUERY_KEY = ["companies", "stats"] as const;
export const companyQueryKey = (companyId: number) => ["companies", companyId] as const;

export interface CompaniesPageResult {
    companies: CompanyListItem[];
    /** From the X-Total-Count response header; 0 if the header is somehow
     * missing rather than throwing, same reasoning as mystic_auth's own
     * useUsersQuery. */
    total: number;
}

export interface CompaniesFilters {
    search?: string;
    hierarchy?: "root" | "subsidiary";
    sortBy?: string;
    sortDir?: SortDirection;
}

export function useCompaniesQuery(page: number, pageSize: number, filters: CompaniesFilters = {}) {
    return useQuery<CompaniesPageResult>({
        queryKey: [...COMPANIES_QUERY_KEY, page, pageSize, filters],
        queryFn: async () => {
            const res = await listCompaniesApi({
                limit: pageSize,
                offset: (page - 1) * pageSize,
                ...filters,
                search: filters.search || undefined,
            });
            const total = Number(res.headers["x-total-count"]);
            return { companies: res.data, total: Number.isFinite(total) ? total : 0 };
        },
        // Keep the current page visible while the next page loads.
        placeholderData: keepPreviousData,
    });
}

/** Aggregate counts for CompanyStatsCard, independent of the main list's
 * current page/filters, so it stays put while those change. */
export function useCompanyStatsQuery() {
    return useQuery({
        queryKey: COMPANY_STATS_QUERY_KEY,
        queryFn: async () => (await getCompanyStatsApi()).data,
    });
}

export function useCompanyQuery(companyId: number, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: companyQueryKey(companyId),
        queryFn: async () => (await getCompanyApi(companyId)).data,
        enabled: options?.enabled,
    });
}

// Autocomplete for the ticker field's "add company" form; `enabled` is the
// caller's debounced-and-long-enough gate, so this never fires per keystroke.
export function useTickerSearchQuery(query: string, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ["companies", "ticker-search", query],
        queryFn: async () => (await searchCompanyTickersApi(query)).data,
        enabled: options?.enabled,
        staleTime: 60_000,
    });
}

export function useCreateCompanyMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (payload: CompanyCreatePayload) => createCompanyApi(payload),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: COMPANIES_QUERY_KEY }),
    });
}

export function useUpdateCompanyMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ companyId, payload }: { companyId: number; payload: CompanyUpdatePayload }) =>
            updateCompanyApi(companyId, payload),
        onSuccess: (_response, { companyId }) => {
            queryClient.invalidateQueries({ queryKey: COMPANIES_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: companyQueryKey(companyId) });
        },
    });
}

export function useDeleteCompanyMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (companyId: number) => deleteCompanyApi(companyId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: COMPANIES_QUERY_KEY }),
    });
}
