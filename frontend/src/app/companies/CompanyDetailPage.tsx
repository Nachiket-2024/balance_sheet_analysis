import React, { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Box, Button, HStack, Input, Stack } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import { PageContainer, DataTable, type DataTableColumn, LoadingState, FormAlert, ConfirmDialog, toaster, IfCan } from "../sdk";
import { TableActionButton, BRAND_SOLID_HOVER_PROPS, SEARCH_INPUT_PROPS } from "../app_sdk";
import { APP_PERMISSIONS } from "../access/permissions";
import { useCompanyQuery } from "./companyQueries";
import {
    useCompanyBalanceSheetsQuery,
    useDeleteBalanceSheetMutation,
    useImportBalanceSheetMutation,
} from "../balance-sheets/balanceSheetQueries";
import type { BalanceSheet } from "../api/balance_sheet_api";
import BalanceSheetChart from "../balance-sheets/BalanceSheetChart";
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
        importMutation.mutate(year, {
            onSuccess: () => {
                toaster.create({ title: t("balance_sheets:importedBalanceSheet", { year }), type: "success" });
                setImportYear("");
            },
            onError: () => toaster.create({ title: t("balance_sheets:importFailed"), type: "error" }),
        });
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
            key: "row_actions",
            header: "",
            align: "end",
            render: (s) => (
                <IfCan action={APP_PERMISSIONS.BALANCE_SHEET_DELETE}>
                    <TableActionButton colorPalette="red" onClick={() => setDeletingYear(s.year)}>
                        {t("balance_sheets:delete")}
                    </TableActionButton>
                </IfCan>
            ),
        },
    ];

    return (
        <>
            {/* Outside PageContainer (which renders the title/description
                first, then children) so this sits above the company name,
                not below it, using the same maxW/centering as PageContainer's own
                Box so it lines up with the title beneath it. */}
            <Box maxW="container.xl" mx="auto" w="full" mb={2}>
                <Button
                    size="sm"
                    variant="solid"
                    colorPalette="brand"
                    onClick={() => navigate("/companies")}
                    {...BRAND_SOLID_HOVER_PROPS}
                >
                    {t("companies:backToCompanies")}
                </Button>
            </Box>

            <PageContainer title={company.name} description={`Ticker: ${company.ticker}`}>

                <IfCan action={APP_PERMISSIONS.BALANCE_SHEET_IMPORT}>
                    <form onSubmit={handleImport}>
                        <HStack mb={6} gap={2}>
                            <Input
                                placeholder={t("balance_sheets:fiscalYearPlaceholder")}
                                value={importYear}
                                onChange={(e) => setImportYear(e.target.value.replace(/\D/g, ""))}
                                type="text"
                                inputMode="numeric"
                                w="220px"
                                {...SEARCH_INPUT_PROPS}
                            />
                            <Button type="submit" colorPalette="brand" loading={importMutation.isPending} {...BRAND_SOLID_HOVER_PROPS}>
                                {t("balance_sheets:importFromYfinance")}
                            </Button>
                        </HStack>
                    </form>
                </IfCan>

                <BalanceSheetChart balanceSheets={balanceSheets ?? []} />

                <DataTable
                    columns={columns}
                    rows={balanceSheets}
                    rowKey={(s) => s.id}
                    isLoading={sheetsLoading}
                    isError={sheetsError}
                    errorMessage={t("balance_sheets:failedToLoadBalanceSheets")}
                    emptyMessage={t("balance_sheets:emptyBalanceSheets")}
                />

                <Stack mt={6}>
                    <IfCan action={APP_PERMISSIONS.LLM_CHAT}>
                        {/* key={companyId} forces a remount when navigating between
                            companies without a full page reload, since React Router
                            re-renders this same route element with a new param
                            rather than unmounting it, so without this the widget's
                            local chat history would otherwise persist across
                            companies. */}
                        <LlmChatWidget key={companyId} companyId={companyId} />
                    </IfCan>
                </Stack>

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
