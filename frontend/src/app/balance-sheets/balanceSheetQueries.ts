import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
    deleteCompanyBalanceSheetApi,
    importCompanyBalanceSheetApi,
    listCompanyBalanceSheetsApi,
} from "../api/balance_sheet_api";

export const companyBalanceSheetsQueryKey = (companyId: number) => ["balance-sheets", companyId] as const;

export function useCompanyBalanceSheetsQuery(companyId: number, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: companyBalanceSheetsQueryKey(companyId),
        queryFn: async () => (await listCompanyBalanceSheetsApi(companyId)).data,
        enabled: options?.enabled,
    });
}

export function useImportBalanceSheetMutation(companyId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (request: number | { year: number; refresh?: boolean }) => {
            if (typeof request === "number") return importCompanyBalanceSheetApi(companyId, request);
            return importCompanyBalanceSheetApi(companyId, request.year, request.refresh ?? false);
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: companyBalanceSheetsQueryKey(companyId) }),
    });
}

export function useDeleteBalanceSheetMutation(companyId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (year: number) => deleteCompanyBalanceSheetApi(companyId, year),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: companyBalanceSheetsQueryKey(companyId) }),
    });
}
