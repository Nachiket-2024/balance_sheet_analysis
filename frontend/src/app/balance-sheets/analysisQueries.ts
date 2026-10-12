import { useQuery } from "@tanstack/react-query";

import { getCompanyBalanceSheetAnalysisApi } from "../api/analysis_api";

export const companyAnalysisQueryKey = (companyId: number, years?: number[], targetCurrency?: string) => targetCurrency ? ["balance-sheet-analysis", companyId, years ?? [], targetCurrency] as const : ["balance-sheet-analysis", companyId, years ?? []] as const;

export function useCompanyAnalysisQuery(companyId: number, years?: number[], targetCurrencyOrOptions?: string | { enabled?: boolean }, options?: { enabled?: boolean }) {
    const targetCurrency = typeof targetCurrencyOrOptions === "string" ? targetCurrencyOrOptions : undefined;
    const queryOptions = typeof targetCurrencyOrOptions === "object" ? targetCurrencyOrOptions : options;
    return useQuery({
        queryKey: companyAnalysisQueryKey(companyId, years, targetCurrency),
        queryFn: async () => (await (targetCurrency ? getCompanyBalanceSheetAnalysisApi(companyId, years, targetCurrency) : getCompanyBalanceSheetAnalysisApi(companyId, years))).data,
        enabled: queryOptions?.enabled,
    });
}
