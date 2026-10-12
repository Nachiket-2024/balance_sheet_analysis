import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FinancialStatement } from "@app/api/financial_statement_api";
import FinancialStatementsPanel from "@app/financial-statements/FinancialStatementsPanel";

const mocks = vi.hoisted(() => ({
    query: { data: [] as FinancialStatement[], isLoading: false, isError: false },
    mutate: vi.fn(),
}));

vi.mock("@app/financial-statements/financialStatementQueries", () => ({
    useCompanyFinancialStatementsQuery: () => mocks.query,
    useImportFinancialStatementMutation: () => ({ mutate: mocks.mutate, isPending: false }),
}));

const statements = [
    { id: 1, company_id: 7, statement_type: "income", year: 2023, total_revenue: 1000, operating_income: 300, net_income: 200 },
    { id: 2, company_id: 7, statement_type: "cash_flow", year: 2023, operating_cash_flow: 250, capital_expenditure: -50, free_cash_flow: 200 },
] as unknown as FinancialStatement[];

describe("FinancialStatementsPanel", () => {
    beforeEach(() => {
        mocks.query = { data: statements, isLoading: false, isError: false };
        mocks.mutate.mockReset();
    });

    it("renders annual income and cash-flow tables and dispatches import and refresh actions", async () => {
        const user = userEvent.setup();
        render(
            <ChakraProvider value={defaultSystem}>
                <FinancialStatementsPanel companyId={7} years={[2023, 2022]} />
            </ChakraProvider>,
        );

        expect(screen.getByRole("heading", { name: "Income statement" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Cash-flow statement" })).toBeInTheDocument();
        expect(screen.getByText("1,000")).toBeInTheDocument();
        expect(screen.getByText("250")).toBeInTheDocument();
        expect(screen.getAllByText("FY 2022").length).toBeGreaterThan(0);

        await user.click(screen.getAllByRole("button", { name: "Refresh" })[0]);
        await user.click(screen.getAllByRole("button", { name: "Import" })[0]);

        expect(mocks.mutate).toHaveBeenNthCalledWith(1, { statementType: "income", year: 2023, refresh: true });
        expect(mocks.mutate).toHaveBeenNthCalledWith(2, { statementType: "income", year: 2022, refresh: false });
    });

    it("shows empty values and handles a query with no data", () => {
        mocks.query = { data: undefined, isLoading: false, isError: false } as never;
        render(
            <ChakraProvider value={defaultSystem}>
                <FinancialStatementsPanel companyId={7} years={[]} />
            </ChakraProvider>,
        );

        expect(screen.getAllByText("No annual statements are available.")).toHaveLength(2);
    });
});
