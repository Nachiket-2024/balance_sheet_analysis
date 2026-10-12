import { api } from "../sdk";

export interface AnalysisMetric {
    value: number | null;
    status: "available" | "unavailable";
    unit: string;
    denominator: string | null;
    source_fields: string[];
    note: string | null;
}

export interface TrendPoint extends AnalysisMetric {
    year: number;
    yoy_change_pct: number | null;
}

export interface AnalysisWarning {
    type: string;
    severity: "info" | "review";
    message: string;
    years: number[];
    evidence: Record<string, number | string | null>;
}

export interface DataQualityIssue {
    code: string;
    severity: "info" | "warning";
    year: number | null;
    fields: string[];
    message: string;
}

export interface BalanceSheetAnalysis {
    company_id: number;
    requested_years: number[] | null;
    fiscal_years: number[];
    unit: string;
    thresholds: Record<string, number>;
    trends: Record<string, TrendPoint[]>;
    metrics: Record<string, AnalysisMetric[]>;
    composition: Record<string, AnalysisMetric[]>;
    source_values: Array<{ year: number; values: Record<string, number | null> }>;
    warnings: AnalysisWarning[];
    data_quality: DataQualityIssue[];
    normalization: { target_currency: string; display_scale: number; used_rates: Array<{ from: string; to: string; rate: number; effective_date: string; source: string; source_url: string | null }>; unavailable_years: number[] } | null;
}

export interface CompanyAnalysisComparison {
    company_id: number;
    company_name: string;
    ticker: string;
    analysis: BalanceSheetAnalysis;
}

export interface BalanceSheetComparison {
    companies: CompanyAnalysisComparison[];
}

export const getCompanyBalanceSheetAnalysisApi = (companyId: number, years?: number[], targetCurrency?: string) =>
    api.get<BalanceSheetAnalysis>(`/balance-sheet-analysis/company/${companyId}`, (() => {
        const params = { ...(years?.length ? { years } : {}), ...(targetCurrency ? { target_currency: targetCurrency } : {}) };
        return Object.keys(params).length ? { params, paramsSerializer: { indexes: null } } : undefined;
    })());

export const compareBalanceSheetAnalysisApi = (companyIds: number[], years?: number[]) =>
    api.get<BalanceSheetComparison>("/balance-sheet-analysis/compare", {
        params: { company_ids: companyIds, ...(years?.length ? { years } : {}) },
        paramsSerializer: { indexes: null },
    });
