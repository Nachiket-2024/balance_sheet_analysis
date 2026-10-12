import React from "react";
import { useTranslation } from "react-i18next";

import { Button, Card, DataTable, type DataTableColumn } from "../sdk";
import { TableActionButton } from "../sdk";
import type { FinancialStatement } from "../api/financial_statement_api";
import { useCompanyFinancialStatementsQuery, useImportFinancialStatementMutation } from "./financialStatementQueries";

const format = (value: number | null) => value === null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

interface StatementYearRow {
    year: number;
    statement?: FinancialStatement;
}

const FinancialStatementsPanel: React.FC<{ companyId: number; years: number[] }> = ({ companyId, years }) => {
    const { t } = useTranslation("balance_sheets");
    const query = useCompanyFinancialStatementsQuery(companyId);
    const mutation = useImportFinancialStatementMutation(companyId);
    const statements = query.data ?? [];
    const income = statements.filter((item) => item.statement_type === "income");
    const cashFlow = statements.filter((item) => item.statement_type === "cash_flow");
    const importStatement = (statementType: "income" | "cash_flow", year: number, refresh = false) =>
        mutation.mutate({ statementType, year, refresh });
    const section = (title: string, records: FinancialStatement[], statementType: "income" | "cash_flow", fields: Array<[keyof FinancialStatement, string]>) => {
        const rows = years.map((year) => ({ year, statement: records.find((item) => item.year === year) }));
        const columns: DataTableColumn<StatementYearRow>[] = [
            { key: "year", header: t("columnYear"), width: "12rem", render: (row) => <span className="font-semibold">FY {row.year}</span> },
            ...fields.map(([field, label]) => ({
                key: String(field), header: label, align: "end" as const, width: "14rem",
                render: (row: StatementYearRow) => <span className="tabular-nums">{row.statement ? format(row.statement[field] as number | null) : "—"}</span>,
            })),
            {
                key: "actions", header: t("financialStatementsAction"), align: "end" as const, width: "11rem",
                render: (row: StatementYearRow) => row.statement
                    ? <TableActionButton colorPalette="blue" onClick={() => importStatement(statementType, row.year, true)}>{t("refresh")}</TableActionButton>
                    : <Button size="sm" variant="outline" onClick={() => importStatement(statementType, row.year)}>{t("importStatement")}</Button>,
            },
        ];
        return (
            <Card className="overflow-hidden p-0">
                <div className="border-b border-border-card px-5 py-4">
                    <h2 className="text-lg font-semibold">{title}</h2>
                    <p className="mt-1 text-sm text-fg-muted">{t("financialStatementsTableDescription", { count: rows.length })}</p>
                </div>
                <div className="p-3 sm:p-4">
                    <DataTable
                        columns={columns}
                        rows={rows}
                        rowKey={(row) => row.year}
                        isLoading={query.isLoading}
                        isError={query.isError}
                        errorMessage={t("financialStatementsFailed")}
                        emptyMessage={t("financialStatementsEmpty")}
                    />
                </div>
            </Card>
        );
    };
    return <div className="mb-6 flex flex-col gap-5">{section(t("incomeStatement"), income, "income", [["total_revenue", t("revenue")], ["operating_income", t("operatingIncome")], ["net_income", t("netIncome")]])}{section(t("cashFlowStatement"), cashFlow, "cash_flow", [["operating_cash_flow", t("operatingCashFlow")], ["capital_expenditure", t("capitalExpenditure")], ["free_cash_flow", t("freeCashFlow")]])}</div>;
};

export default FinancialStatementsPanel;
