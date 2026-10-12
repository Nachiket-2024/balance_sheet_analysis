import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import MockAdapter from "axios-mock-adapter";
import { beforeEach, describe, expect, it } from "vitest";

import api from "@/api/axiosInstance";
import ComparisonPage from "@app/companies/ComparisonPage";

const mock = new MockAdapter(api);
const companies = [
    { id: 1, name: "Microsoft Corporation", ticker: "MSFT", parent_company_id: null, group_root_id: 1 },
    { id: 2, name: "GitHub, Inc.", ticker: "GITHUB.DEMO", parent_company_id: 1, group_root_id: 1 },
    { id: 3, name: "LinkedIn Corporation", ticker: "LINKEDIN.DEMO", parent_company_id: 1, group_root_id: 1 },
];

function analysis(companyId: number, assets: number, warningCount: number) {
    return {
        company_id: companyId,
        requested_years: null,
        fiscal_years: [2023],
        unit: "USD",
        thresholds: {},
        trends: {
            total_assets: [{ year: 2023, value: assets, status: "available", unit: "USD", denominator: null, source_fields: ["total_assets"], note: null, yoy_change_pct: null }],
            stockholders_equity: [{ year: 2023, value: assets / 2, status: "available", unit: "USD", denominator: null, source_fields: ["stockholders_equity"], note: null, yoy_change_pct: null }],
        },
        metrics: {}, composition: {}, source_values: [], data_quality: [], normalization: null,
        warnings: Array.from({ length: warningCount }, (_, index) => ({
            type: `warning_${index}`, severity: "review", message: "Review this balance sheet", years: [2023], evidence: {},
        })),
    };
}

function renderPage() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={queryClient}>
            <ChakraProvider value={defaultSystem}>
                <MemoryRouter><ComparisonPage /></MemoryRouter>
            </ChakraProvider>
        </QueryClientProvider>,
    );
}

describe("ComparisonPage", () => {
    beforeEach(() => {
        mock.reset();
        mock.onGet("/companies/").reply(200, companies, { "X-Total-Count": String(companies.length) });
        mock.onGet("/balance-sheet-analysis/compare").reply((config) => {
            const ids: number[] = (config.params?.company_ids ?? []).map((value: number | string) => Number(value));
            return [200, { companies: ids.map((id) => ({
                company_id: id,
                company_name: companies.find((company) => company.id === id)?.name,
                ticker: companies.find((company) => company.id === id)?.ticker,
                analysis: analysis(id, id * 100, id === 1 ? 2 : 0),
            })) }];
        });
    });

    it("searches the picker and compares selected companies with warning counts", async () => {
        const user = userEvent.setup();
        renderPage();

        expect(await screen.findByText("Microsoft Corporation")).toBeInTheDocument();
        await user.type(screen.getByRole("textbox", { name: "Find a company by name or ticker" }), "GitHub");
        expect(screen.getByText("GitHub, Inc.")).toBeInTheDocument();
        expect(screen.queryByText("LinkedIn Corporation")).toBeNull();

        await user.clear(screen.getByRole("textbox", { name: "Find a company by name or ticker" }));
        await user.click(screen.getByRole("checkbox", { name: /Microsoft Corporation/ }));
        await user.click(screen.getByRole("checkbox", { name: /GitHub, Inc\./ }));

        expect(await screen.findByRole("heading", { name: "Comparison results" })).toBeInTheDocument();
        await waitFor(() => expect(mock.history.get.some((request) => request.url === "/balance-sheet-analysis/compare")).toBe(true));
        expect(screen.getAllByText("2", { selector: "p" })).toHaveLength(2);
        expect(screen.getByText("200")).toBeInTheDocument();
        expect(screen.getAllByText("100")).toHaveLength(2);
        expect(screen.getAllByText("GITHUB.DEMO")).toHaveLength(2);
    });
});
