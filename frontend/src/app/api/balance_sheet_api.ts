import api from "@/api/axiosInstance";

/**
 * Only the fields this app's UI actually reads are typed explicitly (the
 * ones charted/tabulated, see CompanyDetailPage); the index signature
 * covers the ~60 other yfinance-sourced figures the backend returns
 * (backend/app/balance_sheets/balance_sheet_schema.py) without retyping
 * every one of them here.
 */
export interface BalanceSheet {
    id: number;
    company_id: number;
    year: number;
    created_at: string;
    total_assets: number | null;
    total_liabilities_net_minority_interest: number | null;
    stockholders_equity: number | null;
    total_debt: number | null;
    current_assets: number | null;
    current_liabilities: number | null;
    cash_and_cash_equivalents: number | null;
    working_capital: number | null;
    [key: string]: number | string | null | undefined;
}

export const listCompanyBalanceSheetsApi = (companyId: number) =>
    api.get<BalanceSheet[]>(`/balance-sheets/company/${companyId}`);

export const getCompanyBalanceSheetApi = (companyId: number, year: number) =>
    api.get<BalanceSheet>(`/balance-sheets/${companyId}/${year}`);

export const importCompanyBalanceSheetApi = (companyId: number, year: number) =>
    api.post<BalanceSheet>(`/balance-sheets/${companyId}/${year}`);

export const deleteCompanyBalanceSheetApi = (companyId: number, year: number) =>
    api.delete(`/balance-sheets/${companyId}/${year}`);
