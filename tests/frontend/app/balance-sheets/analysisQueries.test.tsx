import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { getCompanyBalanceSheetAnalysisApi } from "@app/api/analysis_api";
import { companyAnalysisQueryKey, useCompanyAnalysisQuery } from "@app/balance-sheets/analysisQueries";

vi.mock("@app/api/analysis_api", () => ({
    getCompanyBalanceSheetAnalysisApi: vi.fn(),
}));

function wrapper() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("analysis query hook", () => {
    it("fetches with all years when no selection is provided", async () => {
        vi.mocked(getCompanyBalanceSheetAnalysisApi).mockResolvedValue({ data: { fiscal_years: [2022, 2023] } } as never);
        const { result } = renderHook(() => useCompanyAnalysisQuery(3), { wrapper: wrapper() });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(getCompanyBalanceSheetAnalysisApi).toHaveBeenCalledWith(3, undefined);
        expect(companyAnalysisQueryKey(3)).toEqual(["balance-sheet-analysis", 3, []]);
    });

    it("supports a selected-year request and disabled state", async () => {
        vi.mocked(getCompanyBalanceSheetAnalysisApi).mockResolvedValue({ data: { fiscal_years: [2023] } } as never);
        const { result } = renderHook(() => useCompanyAnalysisQuery(3, [2023], { enabled: false }), { wrapper: wrapper() });

        expect(result.current.fetchStatus).toBe("idle");
        expect(companyAnalysisQueryKey(3, [2023])).toEqual(["balance-sheet-analysis", 3, [2023]]);
        expect(getCompanyBalanceSheetAnalysisApi).not.toHaveBeenCalled();
    });

    it("passes target currency through the query key and API request", async () => {
        vi.mocked(getCompanyBalanceSheetAnalysisApi).mockResolvedValue({ data: { fiscal_years: [2023] } } as never);
        const { result } = renderHook(() => useCompanyAnalysisQuery(3, [2023], "USD", { enabled: true }), { wrapper: wrapper() });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(getCompanyBalanceSheetAnalysisApi).toHaveBeenCalledWith(3, [2023], "USD");
        expect(companyAnalysisQueryKey(3, [2023], "USD")).toEqual(["balance-sheet-analysis", 3, [2023], "USD"]);
    });
});
