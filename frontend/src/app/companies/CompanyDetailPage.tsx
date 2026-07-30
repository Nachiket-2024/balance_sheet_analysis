import React, { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Box, Button, HStack, Input, Stack } from "@chakra-ui/react";

import { PageContainer, DataTable, type DataTableColumn, LoadingState, FormAlert, ConfirmDialog, toaster, IfCan } from "../sdk";
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

    if (companyLoading) return <LoadingState message="Loading company..." />;
    if (companyError || !company) return <FormAlert status="error">Failed to load company</FormAlert>;

    const handleImport = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        const year = Number(importYear);
        if (!year) return;
        importMutation.mutate(year, {
            onSuccess: () => {
                toaster.create({ title: `Imported ${year} balance sheet`, type: "success" });
                setImportYear("");
            },
            onError: () => toaster.create({ title: "Import failed, check the ticker/year on yfinance", type: "error" }),
        });
    };

    const handleDeleteConfirm = () => {
        if (deletingYear === null) return;
        deleteMutation.mutate(deletingYear, {
            onSuccess: () => {
                toaster.create({ title: `Deleted ${deletingYear} balance sheet`, type: "success" });
                setDeletingYear(null);
            },
            onError: () => toaster.create({ title: "Delete failed", type: "error" }),
        });
    };

    const columns: DataTableColumn<BalanceSheet>[] = [
        { key: "year", header: "Year", render: (s) => s.year },
        {
            key: "total_assets",
            header: "Total assets",
            render: (s) => s.total_assets?.toLocaleString() ?? "—",
        },
        {
            key: "total_liabilities",
            header: "Total liabilities",
            render: (s) => s.total_liabilities_net_minority_interest?.toLocaleString() ?? "—",
        },
        {
            key: "equity",
            header: "Stockholders' equity",
            render: (s) => s.stockholders_equity?.toLocaleString() ?? "—",
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            render: (s) => (
                <IfCan action={APP_PERMISSIONS.BALANCE_SHEET_DELETE}>
                    <Button size="xs" variant="outline" colorPalette="red" onClick={() => setDeletingYear(s.year)}>
                        Delete
                    </Button>
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
                <Button size="sm" variant="solid" colorPalette="brand" onClick={() => navigate("/companies")}>
                    ← Back to companies
                </Button>
            </Box>

            <PageContainer title={company.name} description={`Ticker: ${company.ticker}`}>
                <BalanceSheetChart balanceSheets={balanceSheets ?? []} />

                <IfCan action={APP_PERMISSIONS.BALANCE_SHEET_IMPORT}>
                    <form onSubmit={handleImport}>
                        <HStack mb={6} gap={2}>
                            <Input
                                placeholder="Fiscal year (e.g. 2024)"
                                value={importYear}
                                onChange={(e) => setImportYear(e.target.value)}
                                type="number"
                                w="220px"
                            />
                            <Button type="submit" colorPalette="brand" loading={importMutation.isPending}>
                                Import from yfinance
                            </Button>
                        </HStack>
                    </form>
                </IfCan>

                <DataTable
                    columns={columns}
                    rows={balanceSheets}
                    rowKey={(s) => s.id}
                    isLoading={sheetsLoading}
                    isError={sheetsError}
                    errorMessage="Failed to load balance sheets"
                    emptyMessage="No balance sheets on file for this company yet"
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
                    title="Delete balance sheet"
                    description={`Delete the ${deletingYear} balance sheet for ${company.name}? This cannot be undone.`}
                    confirmLabel="Delete"
                    isLoading={deleteMutation.isPending}
                    onConfirm={handleDeleteConfirm}
                    onCancel={() => setDeletingYear(null)}
                />
            </PageContainer>
        </>
    );
};

export default CompanyDetailPage;
