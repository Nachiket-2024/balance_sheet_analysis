import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import BalanceSheetAnalysisPanel from "@app/balance-sheets/BalanceSheetAnalysisPanel";

const queryState = vi.hoisted(() => ({ data: undefined as unknown, isLoading: false, isError: false }));

vi.mock("@app/balance-sheets/analysisQueries", () => ({
    useCompanyAnalysisQuery: () => queryState,
}));

const metric = (value: number | null, unit = "reported currency units") => ({
    value,
    status: value === null ? "unavailable" : "available",
    unit,
    denominator: null,
    source_fields: ["total_assets"],
    note: value === null ? "Required source field is missing" : null,
});

function analysisFixture() {
    const trend = [
        { ...metric(100), year: 2022, yoy_change_pct: null },
        { ...metric(105), source_fields: [], year: 2023, yoy_change_pct: 5 },
    ];
    const metricSeries = { current_ratio: [{ ...metric(2, "ratio"), denominator: "current liabilities" }], quick_ratio: [metric(1, "ratio")], cash_ratio: [metric(0.5, "ratio")], working_capital: [metric(20)], debt_to_equity: [metric(0.4, "ratio")], debt_to_assets: [metric(0.2, "ratio")] };
    const composition = { cash_as_pct_assets: [metric(10, "percent")], receivables_as_pct_assets: [metric(10, "percent")], inventory_as_pct_assets: [metric(5, "percent")], fixed_assets_as_pct_assets: [metric(25, "percent")], current_assets_as_pct_assets: [metric(50, "percent")], current_liabilities_as_pct_liabilities: [metric(30, "percent")], current_liabilities_as_pct_assets: [metric(15, "percent")], equity_as_pct_assets: [metric(60, "percent")], debt_as_pct_assets: [metric(20, "percent")] };
    return {
        company_id: 1,
        requested_years: null,
        fiscal_years: [2022],
        unit: "reported currency units",
        thresholds: {},
        trends: { total_assets: trend, total_liabilities: trend, stockholders_equity: trend, cash_and_short_term_investments: trend, current_assets: trend, current_liabilities: trend, total_debt: trend, net_debt: trend, receivables: trend, inventory: trend },
        metrics: metricSeries,
        composition,
        source_values: [{ year: 2022, values: { total_assets: 100, current_assets: 50, missing_value: null } }],
        warnings: [{ type: "falling_cash", severity: "review", message: "Cash fell", years: [2022], evidence: { end_value: 80 } }],
        data_quality: [{ code: "missing_core_fields", severity: "warning", year: 2022, fields: ["stockholders_equity"], message: "Core field missing" }],
    };
}

describe("BalanceSheetAnalysisPanel", () => {
    it("explains that analysis needs imported data", () => {
        queryState.data = undefined;
        queryState.isLoading = false;
        queryState.isError = false;
        const { getByText } = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[]} />
            </ChakraProvider>,
        );

        expect(getByText("Balance-sheet analysis")).toBeInTheDocument();
        expect(getByText("Import at least one fiscal year to calculate analysis.")).toBeInTheDocument();
    });

    it("renders deterministic metrics, source values, warnings, and data quality", () => {
        queryState.data = analysisFixture();
        queryState.isLoading = false;
        queryState.isError = false;

        const { getByText, getByDisplayValue } = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[2022, 2023]} />
            </ChakraProvider>,
        );

        expect(getByText("Balance-sheet analysis")).toBeInTheDocument();
        expect(getByText("Liquidity")).toBeInTheDocument();
        expect(getByText("Cash fell")).toBeInTheDocument();
        expect(getByText(/Core field missing/)).toBeInTheDocument();
        expect(getByText("total_assets:")).toBeInTheDocument();
        expect(getByDisplayValue("2022")).toBeInTheDocument();
    });

    it("shows loading, error, and no-selected-year states", () => {
        queryState.data = undefined;
        queryState.isLoading = true;
        queryState.isError = false;
        const loading = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[2022, 2023]} />
            </ChakraProvider>,
        );
        expect(loading.getByText("Calculating analysis…")).toBeInTheDocument();
        loading.unmount();

        queryState.isLoading = false;
        queryState.isError = true;
        const failed = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[2022]} />
            </ChakraProvider>,
        );
        expect(failed.getByText("Analysis could not be loaded.")).toBeInTheDocument();
        failed.unmount();

        queryState.isError = false;
        const noSelection = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[]} />
            </ChakraProvider>,
        );
        expect(noSelection.getByText("Import at least one fiscal year to calculate analysis.")).toBeInTheDocument();
    });

    it("handles an empty server result and a user clearing the year selection", async () => {
        queryState.isLoading = false;
        queryState.isError = false;
        queryState.data = { ...analysisFixture(), fiscal_years: [], warnings: [], data_quality: [] };
        const empty = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[2022]} />
            </ChakraProvider>,
        );
        expect(empty.getByText("No selected fiscal-year data is available.")).toBeInTheDocument();
        empty.unmount();

        queryState.data = { ...analysisFixture(), warnings: [], data_quality: [], metrics: { ...analysisFixture().metrics, current_ratio: [metric(null, "ratio")] } };
        const user = userEvent.setup();
        const populated = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[2022]} />
            </ChakraProvider>,
        );
        expect(populated.getByText("No deterministic review flags were triggered for the selected years.")).toBeInTheDocument();
        expect(populated.getAllByText("Unavailable").length).toBeGreaterThan(0);
        await user.deselectOptions(populated.getByRole("listbox"), "2022");
        expect(populated.getByText("No selected fiscal-year data is available.")).toBeInTheDocument();
    });

    it("shows currency normalization details and unavailable periods", () => {
        queryState.data = {
            ...analysisFixture(),
            normalization: { target_currency: "USD", unavailable_years: [2022] },
        };
        const { getByText } = render(
            <ChakraProvider value={defaultSystem}>
                <BalanceSheetAnalysisPanel companyId={1} availableYears={[2022]} />
            </ChakraProvider>,
        );

        expect(getByText(/Values normalized to USD/)).toBeInTheDocument();
        expect(getByText(/No recorded rate was available for FY 2022/)).toBeInTheDocument();
    });
});
