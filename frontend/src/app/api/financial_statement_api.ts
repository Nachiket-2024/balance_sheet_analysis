import { api } from "../sdk";

export type FinancialStatementType = "income" | "cash_flow";

export interface FinancialStatement {
    id: number;
    company_id: number;
    statement_type: FinancialStatementType;
    year: number;
    period_number: number;
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
    total_revenue: number | null;
    gross_profit: number | null;
    operating_income: number | null;
    ebitda: number | null;
    pretax_income: number | null;
    net_income: number | null;
    operating_cash_flow: number | null;
    capital_expenditure: number | null;
    free_cash_flow: number | null;
    investing_cash_flow: number | null;
    financing_cash_flow: number | null;
    end_cash_position: number | null;
}

export const listCompanyFinancialStatementsApi = (companyId: number, periodType?: string) =>
    api.get<FinancialStatement[]>(`/financial-statements/company/${companyId}`, { params: periodType ? { period_type: periodType } : undefined });

export const importFinancialStatementApi = (
    companyId: number,
    statementType: FinancialStatementType,
    year: number,
    refresh = false,
) => api.post<FinancialStatement>(
    `/financial-statements/${companyId}/${statementType}/${year}`,
    undefined,
    refresh ? { params: { refresh: true } } : undefined,
);
