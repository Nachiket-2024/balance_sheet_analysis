import { Button, Stack } from "@chakra-ui/react";
import type { NavigateFunction } from "react-router";
import type { TFunction } from "i18next";

import { type DataTableColumn, IfCan } from "../sdk";
import { TableActionButton, BRAND_OUTLINE_HOVER_PROPS } from "../app_sdk";
import { APP_PERMISSIONS } from "../access/permissions";
import type { CompanyListItem } from "../api/company_api";

interface BuildCompanyColumnsArgs {
    t: TFunction;
    navigate: NavigateFunction;
    onEdit: (company: CompanyListItem) => void;
    onDelete: (company: CompanyListItem) => void;
}

export function buildCompanyColumns({ t, navigate, onEdit, onDelete }: BuildCompanyColumnsArgs): DataTableColumn<CompanyListItem>[] {
    return [
        { key: "name", header: t("columnName"), sortable: true, render: (c) => c.name },
        { key: "ticker", header: t("columnTicker"), sortable: true, render: (c) => c.ticker },
        {
            key: "parent",
            header: t("columnParentCompany"),
            sortable: true,
            render: (c) => c.parent_name ?? "—",
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            render: (c) => (
                <Stack direction="row" gap={2} justify="flex-end">
                    <Button
                        size="xs"
                        variant="outline"
                        borderColor="brand.fg"
                        color="brand.fg"
                        onClick={() => navigate(`/companies/${c.id}`)}
                        {...BRAND_OUTLINE_HOVER_PROPS}
                    >
                        {t("view")}
                    </Button>
                    <IfCan action={APP_PERMISSIONS.COMPANY_UPDATE}>
                        <TableActionButton colorPalette="orange" onClick={() => onEdit(c)}>
                            {t("edit")}
                        </TableActionButton>
                    </IfCan>
                    <IfCan action={APP_PERMISSIONS.COMPANY_DELETE}>
                        <TableActionButton colorPalette="red" onClick={() => onDelete(c)}>
                            {t("delete")}
                        </TableActionButton>
                    </IfCan>
                </Stack>
            ),
        },
    ];
}
