import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
    importFinancialStatementApi,
    listCompanyFinancialStatementsApi,
    type FinancialStatementType,
} from "../api/financial_statement_api";

export const companyFinancialStatementsQueryKey = (companyId: number) => ["financial-statements", companyId] as const;

export function useCompanyFinancialStatementsQuery(companyId: number, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: companyFinancialStatementsQueryKey(companyId),
        queryFn: async () => (await listCompanyFinancialStatementsApi(companyId, "annual")).data,
        enabled: options?.enabled,
    });
}

export function useImportFinancialStatementMutation(companyId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ statementType, year, refresh = false }: { statementType: FinancialStatementType; year: number; refresh?: boolean }) =>
            importFinancialStatementApi(companyId, statementType, year, refresh),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: companyFinancialStatementsQueryKey(companyId) }),
    });
}
