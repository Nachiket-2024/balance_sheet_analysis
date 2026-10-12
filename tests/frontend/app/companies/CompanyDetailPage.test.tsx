import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CompanyDetailPage from "@app/companies/CompanyDetailPage";

type CompanyQueryState = {
    data: { id: number; name: string; ticker: string } | undefined;
    isLoading: boolean;
    isError: boolean;
};

const state = vi.hoisted(() => ({
    company: { data: { id: 7, name: "Example Co", ticker: "EXAMPLE" } as { id: number; name: string; ticker: string } | undefined, isLoading: false, isError: false } as CompanyQueryState,
    sheets: { data: [{ id: 1, company_id: 7, year: 2023, total_assets: 100 }], isLoading: false, isError: false },
    importMutation: { isPending: false, mutate: vi.fn() },
    deleteMutation: { isPending: false, mutate: vi.fn() },
}));

vi.mock("@app/companies/companyQueries", () => ({
    useCompanyQuery: () => state.company,
}));
vi.mock("@app/balance-sheets/balanceSheetQueries", () => ({
    useCompanyBalanceSheetsQuery: () => state.sheets,
    useDeleteBalanceSheetMutation: () => state.deleteMutation,
    useImportBalanceSheetMutation: () => state.importMutation,
}));
vi.mock("@app/balance-sheets/BalanceSheetChart", () => ({ default: () => <div>Chart</div> }));
vi.mock("@app/balance-sheets/BalanceSheetAnalysisPanel", () => ({ default: () => <div>Analysis panel</div> }));
vi.mock("@app/financial-statements/FinancialStatementsPanel", () => ({ default: () => <div>Financial statements panel</div> }));
vi.mock("@app/reviews/ReviewReportPanel", () => ({ default: () => <div>Review report panel</div> }));
vi.mock("@app/llm/LlmChatWidget", () => ({ default: () => <div>LLM widget</div> }));
vi.mock("@app/sdk", () => ({
    Button: ({ children, onClick, type = "button" }: { children: React.ReactNode; onClick?: () => void; type?: "button" | "submit" }) => <button type={type} onClick={onClick}>{children}</button>,
    TableActionButton: ({ children, onClick }: { children: React.ReactNode; onClick: () => void }) => <button onClick={onClick}>{children}</button>,
    Card: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
    Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
    PageContainer: ({ children, title }: { children: React.ReactNode; title: string }) => <main><h1>{title}</h1>{children}</main>,
    DataTable: ({ columns, rows, rowKey }: { columns: Array<{ render: (row: unknown) => React.ReactNode }>; rows: unknown[]; rowKey: (row: unknown) => number }) => <div>Balance-sheet table{rows.map((row) => <div key={rowKey(row)}>{columns.map((column, index) => <span key={index}>{column.render(row)}</span>)}</div>)}</div>,
    LoadingState: ({ message }: { message: string }) => <div>{message}</div>,
    FormAlert: ({ children }: { children: React.ReactNode }) => <div role="alert">{children}</div>,
    ConfirmDialog: ({ isOpen, onConfirm, onCancel }: { isOpen: boolean; onConfirm: () => void; onCancel: () => void }) => isOpen ? <div><button onClick={onConfirm}>Confirm delete</button><button onClick={onCancel}>Cancel delete</button></div> : null,
    toaster: { create: vi.fn() },
    IfCan: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

function renderPage() {
    return render(
        <ChakraProvider value={defaultSystem}>
            <MemoryRouter initialEntries={["/companies/7"]}>
                <Routes><Route path="/companies/:companyId" element={<CompanyDetailPage />} /></Routes>
            </MemoryRouter>
        </ChakraProvider>,
    );
}

describe("CompanyDetailPage", () => {
    beforeEach(() => {
        state.company = { data: { id: 7, name: "Example Co", ticker: "EXAMPLE" }, isLoading: false, isError: false };
        state.sheets = { data: [{ id: 1, company_id: 7, year: 2023, total_assets: 100 }], isLoading: false, isError: false };
        state.importMutation = { isPending: false, mutate: vi.fn() };
        state.deleteMutation = { isPending: false, mutate: vi.fn() };
    });

    it("renders the company detail and downstream analysis areas", async () => {
        renderPage();

        expect(screen.getByRole("heading", { name: "Example Co" })).toBeInTheDocument();
        expect(screen.getByText("Chart")).toBeInTheDocument();
        expect(screen.getByText("Analysis panel")).toBeInTheDocument();
        expect(screen.getByText("Balance-sheet table")).toBeInTheDocument();
        expect(screen.getByText("LLM widget")).toBeInTheDocument();
        const user = userEvent.setup();
        await user.click(screen.getByRole("button", { name: /Back to companies/ }));
    });

    it("validates and submits fiscal-year import, and confirms deletion", async () => {
        state.importMutation.mutate = vi.fn((_year, options) => options?.onSuccess?.());
        state.deleteMutation.mutate = vi.fn((_year, options) => options?.onSuccess?.());
        const page = renderPage();
        const user = userEvent.setup();
        const input = screen.getByPlaceholderText("Fiscal year (e.g. 2024)");

        await user.type(input, "2024abc");
        await user.click(screen.getByRole("button", { name: "Import from yfinance" }));
        expect(state.importMutation.mutate).toHaveBeenCalledWith({ year: 2024, refresh: false }, expect.any(Object));

        await user.click(screen.getByRole("button", { name: "Delete" }));
        expect(screen.getByRole("button", { name: "Confirm delete" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Cancel delete" }));
        await user.click(screen.getByRole("button", { name: "Delete" }));
        await user.click(screen.getByRole("button", { name: "Confirm delete" }));
        expect(state.deleteMutation.mutate).toHaveBeenCalledWith(2023, expect.any(Object));
        page.unmount();
    });

    it("does not submit a blank import and handles mutation failures", async () => {
        state.importMutation.mutate = vi.fn((_year, options) => options?.onError?.(new Error("import failed")));
        state.deleteMutation.mutate = vi.fn((_year, options) => options?.onError?.(new Error("delete failed")));
        renderPage();
        const user = userEvent.setup();

        await user.click(screen.getByRole("button", { name: "Import from yfinance" }));
        expect(state.importMutation.mutate).not.toHaveBeenCalled();
        await user.type(screen.getByPlaceholderText("Fiscal year (e.g. 2024)"), "2024");
        await user.click(screen.getByRole("button", { name: "Import from yfinance" }));
        await user.click(screen.getByRole("button", { name: "Delete" }));
        await user.click(screen.getByRole("button", { name: "Confirm delete" }));
        expect(state.deleteMutation.mutate).toHaveBeenCalledWith(2023, expect.any(Object));
    });

    it("reports failures when refreshing a saved period", async () => {
        state.importMutation.mutate = vi.fn((_period, options) => options?.onError?.(new Error("refresh failed")));
        renderPage();
        const user = userEvent.setup();

        await user.click(screen.getByRole("button", { name: "Refresh" }));
        expect(state.importMutation.mutate).toHaveBeenCalledWith({ year: 2023, refresh: true }, expect.any(Object));
        expect(state.importMutation.mutate.mock.calls[0][1]?.onError).toBeTypeOf("function");

    });

    it("renders loading and error states for the company query", () => {
        state.company = { data: undefined, isLoading: true, isError: false };
        const loading = renderPage();
        expect(screen.getByText("Loading company...")).toBeInTheDocument();
        loading.unmount();

        state.company = { data: undefined, isLoading: false, isError: true };
        renderPage();
        expect(screen.getByRole("alert")).toHaveTextContent("Failed to load company");
    });

    it("shows the load error when the route id is invalid or the company is absent", () => {
        state.company = { data: undefined, isLoading: false, isError: false };
        render(
            <ChakraProvider value={defaultSystem}>
                <MemoryRouter initialEntries={["/companies/not-a-number"]}>
                    <Routes><Route path="/companies/:companyId" element={<CompanyDetailPage />} /></Routes>
                </MemoryRouter>
            </ChakraProvider>,
        );
        expect(screen.getByRole("alert")).toHaveTextContent("Failed to load company");
    });
});
