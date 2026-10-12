import { beforeEach, describe, expect, it } from "vitest";
import MockAdapter from "axios-mock-adapter";

import api from "@/api/axiosInstance";
import { compareBalanceSheetAnalysisApi, getCompanyBalanceSheetAnalysisApi } from "@app/api/analysis_api";

const mock = new MockAdapter(api);

describe("getCompanyBalanceSheetAnalysisApi", () => {
    beforeEach(() => mock.reset());

    it("requests all years without a years query when no selection is supplied", async () => {
        mock.onGet("/balance-sheet-analysis/company/7").reply((config) => {
            expect(config.params).toBeUndefined();
            return [200, { company_id: 7, fiscal_years: [2022, 2023] }];
        });

        const response = await getCompanyBalanceSheetAnalysisApi(7);

        expect(response.data.fiscal_years).toEqual([2022, 2023]);
    });

    it("serializes selected years as repeated query parameters", async () => {
        mock.onGet("/balance-sheet-analysis/company/7").reply((config) => {
            expect(config.params).toEqual({ years: [2022, 2023] });
            return [200, { company_id: 7, requested_years: [2022, 2023] }];
        });

        const response = await getCompanyBalanceSheetAnalysisApi(7, [2022, 2023]);

        expect(response.data.requested_years).toEqual([2022, 2023]);
    });

    it("passes an explicit target currency for auditable normalization", async () => {
        mock.onGet("/balance-sheet-analysis/company/7").reply((config) => {
            expect(config.params).toEqual({ target_currency: "EUR" });
            return [200, { company_id: 7, normalization: { target_currency: "EUR" } }];
        });

        const response = await getCompanyBalanceSheetAnalysisApi(7, undefined, "EUR");

        expect(response.data.normalization?.target_currency).toBe("EUR");
    });

    it("serializes selected years and target currency together", async () => {
        mock.onGet("/balance-sheet-analysis/company/7").reply((config) => {
            expect(config.params).toEqual({ years: [2022, 2023], target_currency: "AUD" });
            return [200, { company_id: 7, requested_years: [2022, 2023] }];
        });

        const response = await getCompanyBalanceSheetAnalysisApi(7, [2022, 2023], "AUD");

        expect(response.data.requested_years).toEqual([2022, 2023]);
    });

    it("propagates authorization failures", async () => {
        mock.onGet("/balance-sheet-analysis/company/99").reply(403, { detail: "Insufficient permissions" });

        await expect(getCompanyBalanceSheetAnalysisApi(99)).rejects.toMatchObject({
            response: { status: 403 },
        });
    });

    it("requests an explicitly selected comparison set", async () => {
        mock.onGet("/balance-sheet-analysis/compare").reply((config) => {
            expect(config.params).toEqual({ company_ids: [7, 8] });
            return [200, { companies: [] }];
        });

        const response = await compareBalanceSheetAnalysisApi([7, 8]);

        expect(response.data.companies).toEqual([]);
    });

    it("serializes years for an explicitly selected comparison set", async () => {
        mock.onGet("/balance-sheet-analysis/compare").reply((config) => {
            expect(config.params).toEqual({ company_ids: [7, 8], years: [2022, 2023] });
            return [200, { companies: [] }];
        });

        const response = await compareBalanceSheetAnalysisApi([7, 8], [2022, 2023]);

        expect(response.data.companies).toEqual([]);
    });
});
