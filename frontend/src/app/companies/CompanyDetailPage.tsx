import React, { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, Building2, RefreshCw, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, PageContainer, DataTable, type DataTableColumn, LoadingState, FormAlert, ConfirmDialog, toaster, IfCan } from "../sdk";
import { TableActionButton } from "../sdk";
import { APP_PERMISSIONS } from "../access/permissions";
import { exportCompanyBalanceSheetsApi } from "../api/balance_sheet_api";
import { useCompanyQuery } from "./companyQueries";
import {
    useCompanyBalanceSheetsQuery,
    useDeleteBalanceSheetMutation,
    useImportBalanceSheetMutation,
} from "../balance-sheets/balanceSheetQueries";
import type { BalanceSheet } from "../api/balance_sheet_api";
import BalanceSheetChart from "../balance-sheets/BalanceSheetChart";
import BalanceSheetAnalysisPanel from "../balance-sheets/BalanceSheetAnalysisPanel";
import FinancialStatementsPanel from "../financial-statements/FinancialStatementsPanel";
import ReviewReportPanel from "../reviews/ReviewReportPanel";
import LlmChatWidget from "../llm/LlmChatWidget";

/**
 * "Review the past multiple balance sheets quickly" (problem statement 1c):
 * one company, every fiscal year on file, charted and tabulated, plus the
 * grounded LLM chat scoped to this same company.
 */
const CompanyDetailPage: React.FC = () => {
    const { t } = useTranslation(["companies", "balance_sheets"]);
    const navigate = useNavigate();
    const { companyId: companyIdParam } = useParams<{ companyId: string }>();
    const companyId = Number(companyIdParam);
    const hasValidCompanyId = Number.isInteger(companyId);

    const { data: company, isLoading: companyLoading, isError: companyError } = useCompanyQuery(companyId, {
        enabled: hasValidCompanyId,
    });
    const {
        data: balanceSheets,
        isLoading: sheetsLoading,
        isError: sheetsError,
    } = useCompanyBalanceSheetsQuery(companyId, { enabled: hasValidCompanyId });

    const importMutation = useImportBalanceSheetMutation(companyId);
    const deleteMutation = useDeleteBalanceSheetMutation(companyId);

    const [importYear, setImportYear] = useState("");
    const [deletingYear, setDeletingYear] = useState<number | null>(null);

    if (companyLoading) return <LoadingState message={t("companies:loadingCompany")} />;
    if (companyError || !company) return <FormAlert status="error">{t("companies:failedToLoadCompany")}</FormAlert>;

    const handleImport = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        const year = Number(importYear);
        if (!year) return;
        importMutation.mutate({ year, refresh: false }, {
            onSuccess: () => {
                toaster.create({ title: t("balance_sheets:importedBalanceSheet", { year }), type: "success" });
                setImportYear("");
            },
            onError: () => toaster.create({ title: t("balance_sheets:importFailed"), type: "error" }),
        });
    };

    const handleRefresh = (year: number) => {
        importMutation.mutate({ year, refresh: true }, {
            onSuccess: () => toaster.create({ title: t("balance_sheets:refreshedBalanceSheet", { year }), type: "success" }),
            onError: () => toaster.create({ title: t("balance_sheets:refreshFailed"), type: "error" }),
        });
    };

    const handleExport = async () => {
        try {
            const response = await exportCompanyBalanceSheetsApi(companyId);
            const url = URL.createObjectURL(response.data);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = `${company.ticker.toLowerCase()}-balance-sheets.csv`;
            anchor.click();
            URL.revokeObjectURL(url);
        } catch {
            toaster.create({ title: t("balance_sheets:exportFailed"), type: "error" });
        }
    };

    const handleDeleteConfirm = () => {
        if (deletingYear === null) return;
        deleteMutation.mutate(deletingYear, {
            onSuccess: () => {
                toaster.create({ title: t("balance_sheets:deletedBalanceSheet", { year: deletingYear }), type: "success" });
                setDeletingYear(null);
            },
            onError: () => toaster.create({ title: t("balance_sheets:deleteFailed"), type: "error" }),
        });
    };

    const columns: DataTableColumn<BalanceSheet>[] = [
        { key: "year", header: t("balance_sheets:columnYear"), render: (s) => s.year },
        {
            key: "total_assets",
            header: t("balance_sheets:columnTotalAssets"),
            render: (s) => s.total_assets?.toLocaleString() ?? "—",
        },
        {
            key: "total_liabilities",
            header: t("balance_sheets:columnTotalLiabilities"),
            render: (s) => s.total_liabilities_net_minority_interest?.toLocaleString() ?? "—",
        },
        {
            key: "equity",
            header: t("balance_sheets:columnEquity"),
            render: (s) => s.stockholders_equity?.toLocaleString() ?? "—",
        },
        {
            key: "provenance",
            header: t("balance_sheets:columnImported"),
            render: (s) => (
                <span title={s.source_url ?? undefined}>
                    {new Date(s.imported_at).toLocaleDateString()} · v{s.version}
                </span>
            ),
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            render: (s) => (
                <div className="flex justify-end gap-2">
                    <IfCan action={APP_PERMISSIONS.BALANCE_SHEET_IMPORT}>
                        <TableActionButton colorPalette="blue" onClick={() => handleRefresh(s.year)}>
                            <RefreshCw aria-hidden="true" />
                            {t("balance_sheets:refresh")}
                        </TableActionButton>
                    </IfCan>
                    <IfCan action={APP_PERMISSIONS.BALANCE_SHEET_DELETE}>
                        <TableActionButton colorPalette="red" onClick={() => setDeletingYear(s.year)}>
                            {t("balance_sheets:delete")}
                        </TableActionButton>
                    </IfCan>
                </div>
            ),
        },
    ];

    const availableAnalysisYears = (balanceSheets ?? []).map((sheet) => sheet.year).sort((a, b) => a - b);
    const latestImported = [...(balanceSheets ?? [])].sort((a, b) => b.year - a.year)[0];

    return (
        <>
            {/* Outside PageContainer (which renders the title/description
                first, then children) so this sits above the company name,
                not below it, using the same maxW/centering as PageContainer's own
                Box so it lines up with the title beneath it. */}
            <div className="mx-auto mb-3 w-full max-w-(--size-page-content)">
                <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate("/companies")}
                >
                    <ArrowLeft aria-hidden="true" />
                    {t("companies:backToCompanies")}
                </Button>
            </div>

            <PageContainer title={company.name} icon={Building2} description={`Ticker: ${company.ticker}`}>

                <IfCan action={APP_PERMISSIONS.BALANCE_SHEET_IMPORT}>
                    <form onSubmit={handleImport}>
                        <div className="mb-6 flex flex-wrap items-center gap-2">
                            <Input
                                placeholder={t("balance_sheets:fiscalYearPlaceholder")}
                                value={importYear}
                                onChange={(e) => setImportYear(e.target.value.replace(/\D/g, ""))}
                                type="text"
                                inputMode="numeric"
                                className="w-56"
                            />
                            <Button type="submit" variant="brand" loading={importMutation.isPending}>
                                <Upload aria-hidden="true" />
                                {t("balance_sheets:importFromYfinance")}
                            </Button>
                            <Button type="button" variant="outline" onClick={handleExport}>
                                {t("balance_sheets:exportCsv")}
                            </Button>
                        </div>
                    </form>
                </IfCan>

                <BalanceSheetChart balanceSheets={balanceSheets ?? []} />

                {latestImported && (
                    <Card className="mb-6 p-5">
                        <h2 className="text-lg font-semibold">{t("balance_sheets:provenanceTitle")}</h2>
                        <div className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                            <p><span className="font-medium">{t("balance_sheets:source")}: </span>{latestImported.source_provider}</p>
                            <p><span className="font-medium">{t("balance_sheets:periodEnd")}: </span>{latestImported.period_end_date ?? "—"}</p>
                            <p><span className="font-medium">{t("balance_sheets:currency")}: </span>{latestImported.currency_code ?? t("balance_sheets:unknown")}</p>
                            <p><span className="font-medium">{t("balance_sheets:unitScale")}: </span>{latestImported.unit_scale}</p>
                        </div>
                        {latestImported.source_url && <a className="mt-3 inline-block text-sm text-brand-fg underline" href={latestImported.source_url} target="_blank" rel="noreferrer">{t("balance_sheets:viewSource")}</a>}
                    </Card>
                )}

                <BalanceSheetAnalysisPanel key={availableAnalysisYears.join(",")} companyId={companyId} availableYears={availableAnalysisYears} />

                {availableAnalysisYears.length > 0 && <FinancialStatementsPanel companyId={companyId} years={availableAnalysisYears} />}
                {availableAnalysisYears.length > 0 && <ReviewReportPanel companyId={companyId} years={availableAnalysisYears} />}

                <DataTable
                    columns={columns}
                    rows={balanceSheets}
                    rowKey={(s) => s.id}
                    isLoading={sheetsLoading}
                    isError={sheetsError}
                    errorMessage={t("balance_sheets:failedToLoadBalanceSheets")}
                    emptyMessage={t("balance_sheets:emptyBalanceSheets")}
                />

                <div className="mt-6">
                    <IfCan action={APP_PERMISSIONS.LLM_CHAT}>
                        {/* key={companyId} forces a remount when navigating between
                            companies without a full page reload, since React Router
                            re-renders this same route element with a new param
                            rather than unmounting it, so without this the widget's
                            local chat history would otherwise persist across
                            companies. */}
                        <LlmChatWidget key={companyId} companyId={companyId} />
                    </IfCan>
                </div>

                <ConfirmDialog
                    isOpen={deletingYear !== null}
                    title={t("balance_sheets:deleteBalanceSheetTitle")}
                    description={t("balance_sheets:deleteBalanceSheetDescription", {
                        year: deletingYear,
                        companyName: company.name,
                    })}
                    confirmLabel={t("balance_sheets:delete")}
                    isLoading={deleteMutation.isPending}
                    onConfirm={handleDeleteConfirm}
                    onCancel={() => setDeletingYear(null)}
                />
            </PageContainer>
        </>
    );
};

export default CompanyDetailPage;
