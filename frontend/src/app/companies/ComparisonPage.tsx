import React, { useMemo, useState } from "react";
import { Scale, TriangleAlert, UsersRound, Workflow } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { Badge, Button, Card, DataTable, Input, PageContainer, type DataTableColumn } from "../sdk";
import { FilterChips, FilterPanel, StatTile, type FilterChip } from "../app_sdk";
import { compareBalanceSheetAnalysisApi, type CompanyAnalysisComparison } from "../api/analysis_api";
import { useCompaniesQuery } from "./companyQueries";

const ComparisonPage: React.FC = () => {
    const { t } = useTranslation("companies");
    const [selectedIds, setSelectedIds] = useState<number[]>([]);
    const [search, setSearch] = useState("");
    const [selectedOnly, setSelectedOnly] = useState(false);
    const { data: companiesData, isLoading: companiesLoading, isError: companiesError } = useCompaniesQuery(1, 1000);
    const companies = companiesData?.companies ?? [];
    const selectedKey = useMemo(() => [...selectedIds].sort((a, b) => a - b), [selectedIds]);
    const comparison = useQuery({
        queryKey: ["balance-sheet-analysis", "compare", selectedKey],
        queryFn: async () => (await compareBalanceSheetAnalysisApi(selectedKey)).data,
        enabled: selectedKey.length >= 2,
    });
    const visibleCompanies = companies.filter((company) => {
        const matchesSearch = `${company.name} ${company.ticker}`.toLowerCase().includes(search.trim().toLowerCase());
        return matchesSearch && (!selectedOnly || selectedIds.includes(company.id));
    });
    const toggleCompany = (companyId: number) => {
        setSelectedIds((current) => current.includes(companyId)
            ? current.filter((id) => id !== companyId)
            : current.length < 20 ? [...current, companyId] : current);
    };
    const rows = comparison.data?.companies ?? [];
    const warningCompanies = rows.filter((item) => item.analysis.warnings.length > 0).length;
    const warningCount = rows.reduce((count, item) => count + item.analysis.warnings.length, 0);
    const filterChips: FilterChip[] = [
        ...(search ? [{ key: "search", label: t("searchChip", { value: search }), onClear: () => setSearch("") }] : []),
        ...(selectedOnly ? [{ key: "selected", label: t("comparisonSelectedOnly"), onClear: () => setSelectedOnly(false) }] : []),
    ];
    const columns: DataTableColumn<CompanyAnalysisComparison>[] = [
        {
            key: "company", header: t("comparisonCompany"), width: "17rem",
            render: (item) => <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{item.company_name}</span><Badge colorPalette="gray" variant="outline" size="sm">{item.ticker}</Badge></div>,
        },
        { key: "latest_year", header: t("comparisonLatestYear"), align: "end", width: "7rem", render: (item) => item.analysis.fiscal_years.at(-1) ?? "—" },
        { key: "assets", header: t("comparisonAssets"), align: "end", width: "10rem", render: (item) => <span className="tabular-nums">{item.analysis.trends.total_assets?.at(-1)?.value?.toLocaleString() ?? "—"}</span> },
        { key: "equity", header: t("comparisonEquity"), align: "end", width: "10rem", render: (item) => <span className="tabular-nums">{item.analysis.trends.stockholders_equity?.at(-1)?.value?.toLocaleString() ?? "—"}</span> },
        { key: "warnings", header: t("comparisonWarnings"), align: "end", width: "8rem", render: (item) => <Badge colorPalette={item.analysis.warnings.length ? "orange" : "green"} variant="subtle">{item.analysis.warnings.length}</Badge> },
    ];

    return (
        <PageContainer title={t("comparisonTitle")} icon={Scale} description={t("comparisonDescription")}>
            <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <StatTile icon={<UsersRound size={18} aria-hidden="true" />} label={t("comparisonSelectedCount")} value={selectedIds.length} isLoading={false} />
                <StatTile icon={<TriangleAlert size={18} aria-hidden="true" />} label={t("comparisonFlaggedCompanies")} value={comparison.data ? warningCompanies : undefined} isLoading={comparison.isLoading} />
                <StatTile icon={<Workflow size={18} aria-hidden="true" />} label={t("comparisonTotalFlags")} value={comparison.data ? warningCount : undefined} isLoading={comparison.isLoading} />
            </div>

            <FilterPanel className="mb-5">
                <div className="flex flex-wrap items-center gap-3">
                    <Input className="w-full sm:w-72" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("comparisonSearchPlaceholder")} aria-label={t("comparisonSearchPlaceholder")} />
                    <Button size="sm" variant={selectedOnly ? "brand-tinted-outline" : "outline"} aria-pressed={selectedOnly} onClick={() => setSelectedOnly((value) => !value)}>
                        {t("comparisonSelectedOnly")}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setSelectedIds([])} disabled={!selectedIds.length}>
                        {t("comparisonClear")}
                    </Button>
                </div>
                <FilterChips chips={filterChips} onClearAll={() => { setSearch(""); setSelectedOnly(false); }} />
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {companiesLoading && <p className="text-sm text-fg-muted">{t("comparisonLoadingCompanies")}</p>}
                    {companiesError && <p role="alert" className="text-sm text-red-500">{t("failedToLoadCompanies")}</p>}
                    {!companiesLoading && !companiesError && visibleCompanies.map((company) => (
                        <label key={company.id} className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors ${selectedIds.includes(company.id) ? "border-brand-solid bg-brand-tile-subtle" : "border-border-card bg-bg-surface hover:border-brand-solid"}`}>
                            <input className="size-4 accent-brand-solid" type="checkbox" checked={selectedIds.includes(company.id)} onChange={() => toggleCompany(company.id)} />
                            <span className="min-w-0"><span className="block truncate font-medium">{company.name}</span><span className="text-xs text-fg-muted">{company.ticker}</span></span>
                        </label>
                    ))}
                    {!companiesLoading && !companiesError && visibleCompanies.length === 0 && <p className="text-sm text-fg-muted">{t("comparisonNoMatches")}</p>}
                </div>
            </FilterPanel>

            {selectedIds.length < 2 ? (
                <Card className="border-dashed p-6 text-center"><p className="font-medium">{t("comparisonNeedsTwo")}</p><p className="mt-1 text-sm text-fg-muted">{t("comparisonSelected", { count: selectedIds.length })}</p></Card>
            ) : (
                <Card className="overflow-hidden p-0">
                    <div className="border-b border-border-card px-5 py-4"><h2 className="text-lg font-semibold">{t("comparisonResultsTitle")}</h2><p className="mt-1 text-sm text-fg-muted">{t("comparisonResultsDescription")}</p></div>
                    <div className="p-3 sm:p-4">
                        <DataTable columns={columns} rows={rows} rowKey={(item) => item.company_id} isLoading={comparison.isLoading} isError={comparison.isError} errorMessage={t("comparisonFailed")} emptyMessage={t("comparisonNoResults")} />
                    </div>
                </Card>
            )}
        </PageContainer>
    );
};

export default ComparisonPage;
