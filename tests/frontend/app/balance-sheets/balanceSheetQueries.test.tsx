import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
    deleteCompanyBalanceSheetApi,
    importCompanyBalanceSheetApi,
    listCompanyBalanceSheetsApi,
} from "@app/api/balance_sheet_api";
import {
    companyBalanceSheetsQueryKey,
    useCompanyBalanceSheetsQuery,
    useDeleteBalanceSheetMutation,
    useImportBalanceSheetMutation,
} from "@app/balance-sheets/balanceSheetQueries";

vi.mock("@app/api/balance_sheet_api", () => ({
    deleteCompanyBalanceSheetApi: vi.fn(),
    importCompanyBalanceSheetApi: vi.fn(),
    listCompanyBalanceSheetsApi: vi.fn(),
}));

function wrapper() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("balance-sheet query hooks", () => {
    it("uses the company key and returns the server rows", async () => {
        vi.mocked(listCompanyBalanceSheetsApi).mockResolvedValue({ data: [{ year: 2023 }] } as never);
        const { result } = renderHook(() => useCompanyBalanceSheetsQuery(7), { wrapper: wrapper() });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(result.current.data).toEqual([{ year: 2023 }]);
        expect(result.current.dataUpdatedAt).toBeGreaterThan(0);
        expect(companyBalanceSheetsQueryKey(7)).toEqual(["balance-sheets", 7]);
    });

    it("runs import and delete mutations for the selected company/year", async () => {
        vi.mocked(importCompanyBalanceSheetApi).mockResolvedValue({ data: { year: 2024 } } as never);
        vi.mocked(deleteCompanyBalanceSheetApi).mockResolvedValue({ data: undefined } as never);
        const { result } = renderHook(
            () => ({ importMutation: useImportBalanceSheetMutation(7), deleteMutation: useDeleteBalanceSheetMutation(7) }),
            { wrapper: wrapper() },
        );

        await result.current.importMutation.mutateAsync(2024);
        await result.current.importMutation.mutateAsync({ year: 2025 });
        await result.current.importMutation.mutateAsync({ year: 2026, refresh: true });
        await result.current.deleteMutation.mutateAsync(2024);
        expect(importCompanyBalanceSheetApi).toHaveBeenCalledWith(7, 2024);
        expect(importCompanyBalanceSheetApi).toHaveBeenCalledWith(7, 2025, false);
        expect(importCompanyBalanceSheetApi).toHaveBeenCalledWith(7, 2026, true);
        expect(deleteCompanyBalanceSheetApi).toHaveBeenCalledWith(7, 2024);
    });
});
