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
    imported_at: string;
    period_end_date: string | null;
    period_type: string;
    source_provider: string;
    source_url: string | null;
    currency_code: string | null;
    unit_scale: number;
    data_quality_status: string;
    source_fields: string[];
    version: number;
    total_assets: number | null;
    total_liabilities_net_minority_interest: number | null;
    stockholders_equity: number | null;
    total_debt: number | null;
    current_assets: number | null;
    current_liabilities: number | null;
    cash_and_cash_equivalents: number | null;
    working_capital: number | null;
    [key: string]: number | string | string[] | null | undefined;
}

export const listCompanyBalanceSheetsApi = (companyId: number) =>
    api.get<BalanceSheet[]>(`/balance-sheets/company/${companyId}`);

export const exportCompanyBalanceSheetsApi = (companyId: number) =>
    api.get<Blob>(`/balance-sheets/company/${companyId}/export.csv`, { responseType: "blob" });

export const getCompanyBalanceSheetApi = (companyId: number, year: number) =>
    api.get<BalanceSheet>(`/balance-sheets/${companyId}/${year}`);

export const importCompanyBalanceSheetApi = (companyId: number, year: number, refresh = false) =>
    api.post<BalanceSheet>(
        `/balance-sheets/${companyId}/${year}`,
        undefined,
        refresh ? { params: { refresh: true } } : undefined,
    );

export const deleteCompanyBalanceSheetApi = (companyId: number, year: number) =>
    api.delete(`/balance-sheets/${companyId}/${year}`);
