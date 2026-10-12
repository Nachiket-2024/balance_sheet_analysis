import React, { useMemo, useState } from "react";
import { BarChart3, CircleAlert, Database, Gauge, Scale, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card, DataTable, type DataTableColumn, FormAlert, Input, LoadingState } from "../sdk";
import type { AnalysisMetric, BalanceSheetAnalysis, TrendPoint } from "../api/analysis_api";
import { useCompanyAnalysisQuery } from "./analysisQueries";

const LABELS: Record<string, string> = {
    total_assets: "Total assets", total_liabilities: "Total liabilities", stockholders_equity: "Stockholders' equity", cash_and_short_term_investments: "Cash & short-term investments", current_assets: "Current assets", current_liabilities: "Current liabilities", total_debt: "Total debt", net_debt: "Net debt", receivables: "Receivables", inventory: "Inventory", current_ratio: "Current ratio", quick_ratio: "Quick ratio", cash_ratio: "Cash ratio", working_capital: "Working capital", debt_to_equity: "Debt / equity", debt_to_assets: "Debt / assets", liabilities_to_assets: "Liabilities / assets", equity_ratio: "Equity ratio", net_debt_to_equity: "Net debt / equity", long_term_debt_share: "Long-term debt share", cash_as_pct_assets: "Cash / assets", receivables_as_pct_assets: "Receivables / assets", inventory_as_pct_assets: "Inventory / assets", fixed_assets_as_pct_assets: "Fixed assets / assets", current_assets_as_pct_assets: "Current assets / assets", current_liabilities_as_pct_liabilities: "Current liabilities / liabilities", current_liabilities_as_pct_assets: "Current liabilities / assets", equity_as_pct_assets: "Equity / assets", debt_as_pct_assets: "Debt / assets",
};
const pickMetrics = <T,>(values: Record<string, T[]>, names: string[]) => Object.fromEntries(names.filter((name) => values[name]).map((name) => [name, values[name]]));
const formatValue = (metric: AnalysisMetric | TrendPoint, percent = false) => metric.value === null || metric.status === "unavailable" ? "Unavailable" : `${metric.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${percent ? "%" : ""}`;
const formatSourceValue = (value: number | null) => value === null ? "Unavailable" : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

const MetricGrid: React.FC<{ values: Record<string, AnalysisMetric[]>; years: number[]; percent?: boolean; label: (name: string) => string }> = ({ values, years, percent = false, label }) => <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
    {Object.entries(values).map(([name, series]) => { const latest = series[series.length - 1]; return <div key={name} className="rounded-md border border-border-card bg-bg-canvas/40 p-3 transition-colors hover:border-brand-solid/60"><p className="text-sm font-semibold">{label(name)}</p><p className="mt-1 text-xl font-semibold tracking-tight">{formatValue(latest, percent)}</p><p className="mt-1 text-xs text-fg-muted">FY {years[years.length - 1]} · {latest?.denominator ? `denominator: ${latest.denominator}` : latest?.unit}</p><p className="text-xs text-fg-muted">Source: {latest?.source_fields.join(", ") || "none"}</p>{latest?.note && <p className="mt-1 text-xs text-fg-muted">{latest.note}</p>}</div>; })}
</div>;

interface TrendRow { name: string; series: TrendPoint[] }

const TrendTable: React.FC<{ analysis: BalanceSheetAnalysis; label: (name: string) => string; metricLabel: string; emptyMessage: string }> = ({ analysis, label, metricLabel, emptyMessage }) => {
    const rows = Object.entries(analysis.trends).map(([name, series]) => ({ name, series }));
    const columns: DataTableColumn<TrendRow>[] = [
        { key: "metric", header: metricLabel, width: "18rem", render: (row) => <span className="font-semibold">{label(row.name)}</span> },
        ...analysis.fiscal_years.map((year) => ({
            key: String(year), header: `FY ${year}`, align: "end" as const, width: "14rem",
            render: (row: TrendRow) => {
                const point = row.series.find((item) => item.year === year);
                return point ? <div className="tabular-nums">{formatValue(point)}<div className="text-xs text-fg-muted">{point.yoy_change_pct === null ? "—" : `${point.yoy_change_pct.toFixed(1)}% YoY`}</div></div> : "—";
            },
        })),
    ];
    return <DataTable columns={columns} rows={rows} rowKey={(row) => row.name} emptyMessage={emptyMessage} />;
};

const SectionCard: React.FC<{ icon: React.ElementType; title: string; children: React.ReactNode }> = ({ icon: Icon, title, children }) => <Card className="p-5"><div className="mb-4 flex items-center gap-2.5"><span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-tile-subtle text-brand-fg"><Icon size={17} aria-hidden="true" /></span><h2 className="text-lg font-semibold tracking-tight">{title}</h2></div>{children}</Card>;

const BalanceSheetAnalysisPanel: React.FC<{ companyId: number; availableYears: number[] }> = ({ companyId, availableYears }) => {
    const { t } = useTranslation("analysis");
    const label = (name: string) => t(`metric_${name}`, { defaultValue: LABELS[name] ?? name });
    const [selectedYears, setSelectedYears] = useState<number[]>(availableYears);
    const [currencyInput, setCurrencyInput] = useState("");
    const [targetCurrency, setTargetCurrency] = useState<string>();
    const { data, isLoading, isError } = useCompanyAnalysisQuery(companyId, selectedYears.length === availableYears.length ? undefined : selectedYears, targetCurrency, { enabled: availableYears.length > 0 && selectedYears.length > 0 });
    const latestYear = data?.fiscal_years[data.fiscal_years.length - 1];
    const selectedLabel = useMemo(() => selectedYears.length ? selectedYears.join(", ") : t("analysisSelectAtLeastOneYear"), [selectedYears, t]);
    if (!availableYears.length) return <Card className="mb-6 p-5"><p className="font-semibold">{t("analysisTitle")}</p><p className="mt-1 text-fg-muted">{t("analysisNeedsData")}</p></Card>;
    if (!selectedYears.length) return <Card className="mb-6 p-5"><p>{t("analysisNoSelectedData")}</p></Card>;
    if (isLoading) return <LoadingState message={t("analysisLoading")} />;
    if (isError || !data) return <FormAlert status="error">{t("analysisFailed")}</FormAlert>;
    if (!data.fiscal_years.length) return <Card className="mb-6 p-5"><p>{t("analysisNoSelectedData")}</p></Card>;
    return <div className="mb-6 flex flex-col gap-5"><select multiple className="sr-only" value={selectedYears.map(String)} onChange={(event) => setSelectedYears(Array.from(event.target.selectedOptions, (option) => Number(option.value)).sort((a, b) => a - b))} aria-label={t("analysisYears")}>{availableYears.map((year) => <option key={year} value={year}>{year}</option>)}</select>
        <Card className="border-t-2 border-t-brand-solid p-5"><div className="flex flex-wrap items-start justify-between gap-5"><div><div className="flex items-center gap-2"><BarChart3 size={20} className="text-brand-fg" aria-hidden="true" /><h2 className="text-xl font-semibold tracking-tight">{t("analysisTitle")}</h2></div><p className="mt-1 text-sm text-fg-muted">{t("analysisSubtitle", { unit: data.unit })}</p></div><div className="min-w-52"><p className="mb-1.5 text-sm font-semibold">{t("analysisYears")}</p><div className="flex flex-wrap gap-1.5" aria-label={t("analysisYears")}>{availableYears.map((year) => { const isSelected = selectedYears.includes(year); return <button type="button" key={year} aria-pressed={isSelected} onClick={() => setSelectedYears((current) => isSelected ? current.filter((item) => item !== year) : [...current, year].sort((a, b) => a - b))} className={`rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors ${isSelected ? "border-brand-solid bg-brand-solid text-brand-contrast" : "border-border-strong bg-bg-canvas text-fg-muted hover:border-brand-solid hover:text-brand-fg"}`}>FY {year}</button>; })}</div><p className="mt-1.5 text-xs text-fg-muted">{selectedLabel}</p></div></div><div className="mt-4 flex flex-wrap items-end gap-2"><div><label className="mb-1 block text-xs font-semibold">{t("analysisCurrency")}</label><Input value={currencyInput} onChange={(event) => setCurrencyInput(event.target.value.toUpperCase())} placeholder={t("analysisCurrencyPlaceholder")} aria-label={t("analysisCurrency")} /></div><Button size="sm" variant="outline" onClick={() => setTargetCurrency(currencyInput.trim() || undefined)}>{t("analysisApplyCurrency")}</Button></div><p className="mt-4 text-sm text-fg-muted">{t("analysisExecutiveSummary", { year: latestYear })}</p><div className="mt-4"><MetricGrid values={pickMetrics(data.trends, ["total_assets", "total_liabilities", "stockholders_equity", "total_debt", "net_debt"])} years={data.fiscal_years} label={label} /></div>{data.normalization && <p className="mt-3 text-xs text-fg-muted">{t("analysisNormalization", { currency: data.normalization.target_currency })}{data.normalization.unavailable_years.length ? ` ${t("analysisNormalizationUnavailable", { years: data.normalization.unavailable_years.join(", ") })}` : ""}</p>}</Card>
        <SectionCard icon={BarChart3} title={t("analysisCoreTrends")}><TrendTable analysis={data} label={label} metricLabel={t("analysisMetricColumn")} emptyMessage={t("analysisTrendEmpty")} /></SectionCard>
        <SectionCard icon={Gauge} title={t("analysisLiquidity")}><MetricGrid values={pickMetrics(data.metrics, ["current_ratio", "quick_ratio", "cash_ratio", "working_capital"])} years={data.fiscal_years} label={label} /></SectionCard>
        <SectionCard icon={Scale} title={t("analysisLeverage")}><MetricGrid values={pickMetrics(data.metrics, ["debt_to_equity", "debt_to_assets", "net_debt_to_equity"])} years={data.fiscal_years} label={label} /></SectionCard>
        <SectionCard icon={ShieldCheck} title={t("analysisSolvency")}><MetricGrid values={pickMetrics(data.metrics, ["liabilities_to_assets", "equity_ratio", "long_term_debt_share"])} years={data.fiscal_years} label={label} /></SectionCard>
        <SectionCard icon={BarChart3} title={t("analysisComposition")}><MetricGrid values={data.composition} years={data.fiscal_years} percent label={label} /></SectionCard>
        <SectionCard icon={Database} title={t("analysisSourceValues")}><p className="mb-3 text-sm text-fg-muted">{t("analysisSourceValuesSubtitle", { unit: data.unit })}</p><div className="flex flex-col gap-3">{data.source_values.map((source) => <div className="rounded-md border border-border-card bg-bg-canvas/40 p-3" key={source.year}><p className="font-semibold">FY {source.year}</p><div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(source.values).filter(([, value]) => value !== null).map(([field, value]) => <p className="text-sm" key={field}><span className="font-medium">{field}:</span> {formatSourceValue(value)}</p>)}</div></div>)}</div></SectionCard>
        <SectionCard icon={CircleAlert} title={t("analysisWarnings")}>{data.warnings.length ? <div className="flex flex-col gap-2">{data.warnings.map((warning) => <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3" key={`${warning.type}-${warning.years.join("-")}`}><p className="font-semibold">{warning.message}</p><p className="mt-1 text-xs text-fg-muted">{t("analysisEvidence")}: {JSON.stringify(warning.evidence)}</p></div>)}</div> : <p className="text-fg-muted">{t("analysisNoWarnings")}</p>}{data.data_quality.length > 0 && <div className="mt-4"><p className="font-semibold">{t("analysisDataQuality")}</p><div className="mt-2 flex flex-col gap-1">{data.data_quality.map((issue, index) => <p className="text-sm text-fg-muted" key={`${issue.code}-${issue.year}-${index}`}>• {issue.message}</p>)}</div></div>}</SectionCard>
    </div>;
};

export default BalanceSheetAnalysisPanel;
