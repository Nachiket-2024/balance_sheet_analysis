import { beforeEach, describe, expect, it } from "vitest";
import MockAdapter from "axios-mock-adapter";

import api from "@/api/axiosInstance";
import { importFinancialStatementApi, listCompanyFinancialStatementsApi } from "@app/api/financial_statement_api";

const mock = new MockAdapter(api);

describe("financial statement API", () => {
    beforeEach(() => mock.reset());

    it("lists statements for a company", async () => {
        mock.onGet("/financial-statements/company/7").reply(200, [{ company_id: 7, statement_type: "income", year: 2023 }]);

        const response = await listCompanyFinancialStatementsApi(7);

        expect(response.data[0]).toMatchObject({ company_id: 7, statement_type: "income" });
    });

    it("filters statements by period type when supplied", async () => {
        mock.onGet("/financial-statements/company/7", { params: { period_type: "annual" } }).reply(200, []);

        const response = await listCompanyFinancialStatementsApi(7, "annual");

        expect(response.data).toEqual([]);
    });

    it("sends an explicit refresh only when requested", async () => {
        mock.onPost("/financial-statements/7/cash_flow/2023", undefined, { params: { refresh: true } }).reply(201, { year: 2023 });

        const response = await importFinancialStatementApi(7, "cash_flow", 2023, true);

        expect(response.status).toBe(201);
    });

    it("omits refresh parameters when refresh is not requested", async () => {
        mock.onPost("/financial-statements/7/income/2023", undefined, undefined).reply(201, { year: 2023 });

        const response = await importFinancialStatementApi(7, "income", 2023);

        expect(response.status).toBe(201);
    });
});
