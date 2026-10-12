import { Building2, Eye, Pencil, Trash2 } from "lucide-react";
import type { NavigateFunction } from "react-router";
import type { TFunction } from "i18next";

import { Badge, Button, type DataTableColumn, IfCan } from "../sdk";
import { TableActionButton } from "../sdk";
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
        { key: "name", header: t("columnName"), sortable: true, width: "34%", render: (c) => <div className="flex items-center gap-2.5"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border-card bg-brand-tile-subtle text-brand-fg"><Building2 size={16} aria-hidden="true" /></span><span className="font-medium">{c.name}</span></div> },
        { key: "ticker", header: t("columnTicker"), sortable: true, width: "18%", render: (c) => <Badge colorPalette="gray" variant="outline" size="sm">{c.ticker}</Badge> },
        {
            key: "parent",
            header: t("columnParentCompany"),
            sortable: true,
            width: "30%",
            render: (c) => c.parent_name ?? "—",
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            width: "18%",
            render: (c) => (
                <div className="flex flex-wrap justify-end gap-1.5">
                    <Button
                        size="xs"
                        variant="outline"
                        onClick={() => navigate(`/companies/${c.id}`)}
                    >
                        <Eye aria-hidden="true" />
                        {t("view")}
                    </Button>
                    <IfCan action={APP_PERMISSIONS.COMPANY_UPDATE}>
                        <TableActionButton colorPalette="orange" onClick={() => onEdit(c)}>
                            <Pencil aria-hidden="true" />
                            {t("edit")}
                        </TableActionButton>
                    </IfCan>
                    <IfCan action={APP_PERMISSIONS.COMPANY_DELETE}>
                        <TableActionButton colorPalette="red" onClick={() => onDelete(c)}>
                            <Trash2 aria-hidden="true" />
                            {t("delete")}
                        </TableActionButton>
                    </IfCan>
                </div>
            ),
        },
    ];
}
