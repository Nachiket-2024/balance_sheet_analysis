import React, { useState } from "react";
import { Button, HStack, Input, Text } from "@chakra-ui/react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";

import { PageContainer, DataTable, ConfirmDialog, toaster, IfCan } from "../sdk";
import { BRAND_SOLID_HOVER_PROPS, StyledSelect, SEARCH_INPUT_PROPS, useSortState, useDebouncedValue, Pagination, usePageResetOn } from "../app_sdk";
import { APP_PERMISSIONS } from "../access/permissions";
import { useCompaniesQuery, useCreateCompanyMutation, useDeleteCompanyMutation, useUpdateCompanyMutation } from "./companyQueries";
import CompanyStatsCard from "./CompanyStatsCard";
import CompanyFormCard from "./CompanyFormCard";
import { useTickerAutofill } from "./useTickerAutofill";
import { buildCompanyColumns } from "./companyColumns";
import type { CompanyListItem } from "../api/company_api";

const PAGE_SIZE = 25;
const ALL_VALUE = "";

const extractErrorDetail = (error: unknown, fallback: string): string =>
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;

/**
 * Every company `current_user` may read. The backend scopes GET /companies/,
 * so this page never needs a client-side permission filter per row.
 *
 * Search/hierarchy-filter/sort all run server-side (see companyQueries.ts),
 * since an admin-scoped user can see an unbounded company list.
 *
 * Ticker-autofill state lives in useTickerAutofill, the form itself in
 * CompanyFormCard, and table column defs in companyColumns - this page owns
 * only page-level state (which row is being edited/deleted, search/sort/pagination).
 */
const CompaniesPage: React.FC = () => {
    const { t } = useTranslation("companies");
    const navigate = useNavigate();
    const createMutation = useCreateCompanyMutation();
    const updateMutation = useUpdateCompanyMutation();
    const deleteMutation = useDeleteCompanyMutation();

    const [showForm, setShowForm] = useState(false);
    const [editingCompany, setEditingCompany] = useState<CompanyListItem | null>(null);
    const [name, setName] = useState("");
    const [parentCompanyId, setParentCompanyId] = useState("");
    const [deletingCompany, setDeletingCompany] = useState<CompanyListItem | null>(null);

    const tickerAutofill = useTickerAutofill(showForm, name, setName, editingCompany?.id, t);

    const [search, setSearch] = useState("");
    // Debounce server-side search so typing does not fire per-character requests.
    const debouncedSearch = useDebouncedValue(search);
    const [hierarchy, setHierarchy] = useState(ALL_VALUE);
    const { sort, toggleSort } = useSortState("");

    // Search/filter/sort changes can invalidate the current page number.
    const [page, setPage] = usePageResetOn(`${debouncedSearch}|${sort.key}|${sort.direction}|${hierarchy}`);

    const { data, isLoading, isError } = useCompaniesQuery(page, PAGE_SIZE, {
        search: debouncedSearch,
        hierarchy: (hierarchy || undefined) as "root" | "subsidiary" | undefined,
        sortBy: sort.key || undefined,
        sortDir: sort.direction,
    });
    const companies = data?.companies;
    const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

    const closeForm = () => {
        setShowForm(false);
        setEditingCompany(null);
        setName("");
        setParentCompanyId("");
        tickerAutofill.reset();
    };

    const openCreateForm = () => {
        setEditingCompany(null);
        setName("");
        setParentCompanyId("");
        tickerAutofill.reset();
        setShowForm(true);
    };

    const openEditForm = (company: CompanyListItem) => {
        setEditingCompany(company);
        setName(company.name);
        tickerAutofill.setTicker(company.ticker);
        setParentCompanyId(company.parent_company_id != null ? String(company.parent_company_id) : "");
        setShowForm(true);
    };

    const formMutation = editingCompany ? updateMutation : createMutation;
    const formErrorMessage = formMutation.isError
        ? extractErrorDetail(formMutation.error, editingCompany ? t("failedToUpdateCompany") : t("failedToCreateCompany"))
        : undefined;

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        const payload = {
            name,
            ticker: tickerAutofill.ticker,
            parent_company_id: parentCompanyId ? Number(parentCompanyId) : null,
        };

        if (editingCompany) {
            updateMutation.mutate(
                { companyId: editingCompany.id, payload },
                {
                    onSuccess: () => {
                        toaster.create({ title: t("companyUpdated"), type: "success" });
                        closeForm();
                    },
                    onError: (error) =>
                        toaster.create({ title: extractErrorDetail(error, t("failedToUpdateCompany")), type: "error" }),
                }
            );
            return;
        }

        createMutation.mutate(payload, {
            onSuccess: () => {
                toaster.create({ title: t("companyCreated"), type: "success" });
                closeForm();
            },
            onError: (error) => toaster.create({ title: extractErrorDetail(error, t("failedToCreateCompany")), type: "error" }),
        });
    };

    const handleDeleteConfirm = () => {
        if (deletingCompany === null) return;
        deleteMutation.mutate(deletingCompany.id, {
            onSuccess: () => {
                toaster.create({ title: t("deletedCompany", { name: deletingCompany.name }), type: "success" });
                setDeletingCompany(null);
            },
            onError: (error) => {
                toaster.create({ title: extractErrorDetail(error, t("failedToDeleteCompany")), type: "error" });
                setDeletingCompany(null);
            },
        });
    };

    const columns = buildCompanyColumns({ t, navigate, onEdit: openEditForm, onDelete: setDeletingCompany });

    return (
        <PageContainer
            title={t("pageTitle")}
            description={t("pageDescription")}
            actions={
                <CompanyStatsCard
                    onFilterTotal={() => {
                        setSearch("");
                        setHierarchy(ALL_VALUE);
                    }}
                    onFilterGroupRoots={() => {
                        setSearch("");
                        setHierarchy("root");
                    }}
                    onFilterSubsidiaries={() => {
                        setSearch("");
                        setHierarchy("subsidiary");
                    }}
                />
            }
            headerExtra={
                <HStack gap={3} wrap="wrap">
                    <Input
                        placeholder={t("searchPlaceholder")}
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        maxW="sm"
                        {...SEARCH_INPUT_PROPS}
                    />

                    <StyledSelect
                        w="160px"
                        ariaLabel={t("scopeFilterAriaLabel")}
                        value={hierarchy}
                        onChange={setHierarchy}
                        options={[
                            { value: ALL_VALUE, label: t("allCompanies") },
                            { value: "root", label: t("groupRoots") },
                            { value: "subsidiary", label: t("subsidiaries") },
                        ]}
                    />

                    <IfCan action={APP_PERMISSIONS.COMPANY_CREATE}>
                        <Button
                            size="sm"
                            colorPalette="brand"
                            onClick={() => (showForm ? closeForm() : openCreateForm())}
                            {...BRAND_SOLID_HOVER_PROPS}
                        >
                            {showForm ? t("cancel") : t("addCompany")}
                        </Button>
                    </IfCan>
                </HStack>
            }
        >
            {showForm && (
                <CompanyFormCard
                    t={t}
                    editingCompany={editingCompany}
                    name={name}
                    setName={setName}
                    parentCompanyId={parentCompanyId}
                    setParentCompanyId={setParentCompanyId}
                    tickerAutofill={tickerAutofill}
                    formMutation={formMutation}
                    formErrorMessage={formErrorMessage}
                    onSubmit={handleSubmit}
                    onCancel={closeForm}
                />
            )}

            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mb={4} />

            <DataTable
                columns={columns}
                rows={companies}
                rowKey={(c) => c.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage={t("failedToLoadCompanies")}
                emptyMessage={search || hierarchy ? t("emptyFiltered") : t("emptyUnfiltered")}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />

            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mt={4} />

            {!isLoading && !isError && data?.total === 0 && (
                <Text color="fg.muted" mt={4} fontSize="sm">
                    {t("noAccess")}
                </Text>
            )}

            <ConfirmDialog
                isOpen={deletingCompany !== null}
                title={t("deleteCompanyTitle")}
                description={t("deleteCompanyDescription", { name: deletingCompany?.name })}
                confirmLabel={t("delete")}
                isLoading={deleteMutation.isPending}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeletingCompany(null)}
            />
        </PageContainer>
    );
};

export default CompaniesPage;
