import React, { useState } from "react";
import { Button, Input, Stack, Text } from "@chakra-ui/react";
import { useNavigate } from "react-router";

import { PageContainer, DataTable, type DataTableColumn, Card, ConfirmDialog, FormAlert, toaster, IfCan } from "../sdk";
import { APP_PERMISSIONS } from "../access/permissions";
import { useCompaniesQuery, useCreateCompanyMutation, useDeleteCompanyMutation } from "./companyQueries";
import type { Company } from "../api/company_api";

const extractErrorDetail = (error: unknown, fallback: string): string =>
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;

/**
 * Every company `current_user` may read, the list is already scoped by
 * the backend (GET /companies/, see company_routes.py's get_company_scope
 * call), so unlike mystic_auth's UsersPage this never needs a client-side
 * permission filter per row: a CEO's response here IS just their company, a
 * group executive's IS their whole group, with nothing further to hide.
 */
const CompaniesPage: React.FC = () => {
    const { data: companies, isLoading, isError } = useCompaniesQuery();
    const navigate = useNavigate();
    const createMutation = useCreateCompanyMutation();
    const deleteMutation = useDeleteCompanyMutation();

    const [showCreateForm, setShowCreateForm] = useState(false);
    const [name, setName] = useState("");
    const [ticker, setTicker] = useState("");
    const [parentCompanyId, setParentCompanyId] = useState("");
    const [deletingCompany, setDeletingCompany] = useState<Company | null>(null);

    const companyById = new Map((companies ?? []).map((c) => [c.id, c]));

    const handleCreate = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        createMutation.mutate(
            {
                name,
                ticker,
                parent_company_id: parentCompanyId ? Number(parentCompanyId) : null,
            },
            {
                onSuccess: () => {
                    toaster.create({ title: "Company created", type: "success" });
                    setName("");
                    setTicker("");
                    setParentCompanyId("");
                    setShowCreateForm(false);
                },
                onError: () => toaster.create({ title: "Failed to create company", type: "error" }),
            }
        );
    };

    const handleDeleteConfirm = () => {
        if (deletingCompany === null) return;
        deleteMutation.mutate(deletingCompany.id, {
            onSuccess: () => {
                toaster.create({ title: `Deleted ${deletingCompany.name}`, type: "success" });
                setDeletingCompany(null);
            },
            onError: (error) => {
                toaster.create({ title: extractErrorDetail(error, "Failed to delete company"), type: "error" });
                setDeletingCompany(null);
            },
        });
    };

    const columns: DataTableColumn<Company>[] = [
        { key: "name", header: "Name", render: (c) => c.name },
        { key: "ticker", header: "Ticker", render: (c) => c.ticker },
        {
            key: "parent",
            header: "Parent company",
            render: (c) => (c.parent_company_id ? companyById.get(c.parent_company_id)?.name ?? "—" : "—"),
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
                        colorPalette="brand"
                        borderColor="brand.600"
                        color="brand.700"
                        onClick={() => navigate(`/companies/${c.id}`)}
                    >
                        View
                    </Button>
                    <IfCan action={APP_PERMISSIONS.COMPANY_DELETE}>
                        <Button size="xs" variant="outline" colorPalette="red" onClick={() => setDeletingCompany(c)}>
                            Delete
                        </Button>
                    </IfCan>
                </Stack>
            ),
        },
    ];

    return (
        <PageContainer
            title="Companies"
            description="Companies and verticals you're assigned to review."
            actions={
                <IfCan action={APP_PERMISSIONS.COMPANY_CREATE}>
                    <Button size="sm" colorPalette="brand" onClick={() => setShowCreateForm((v) => !v)}>
                        {showCreateForm ? "Cancel" : "Add company"}
                    </Button>
                </IfCan>
            }
        >
            {showCreateForm && (
                <Card p={5} mb={6}>
                    <form onSubmit={handleCreate}>
                        <Stack gap={3}>
                            <Input
                                placeholder="Company name (e.g. Jio Platforms)"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                            />
                            <Input
                                placeholder="Ticker (e.g. JIO.NS)"
                                value={ticker}
                                onChange={(e) => setTicker(e.target.value)}
                                required
                            />
                            <Input
                                placeholder="Parent company ID (optional, leave blank for a group root)"
                                value={parentCompanyId}
                                onChange={(e) => setParentCompanyId(e.target.value)}
                                type="number"
                            />
                            {createMutation.isError && (
                                <FormAlert status="error">
                                    {extractErrorDetail(createMutation.error, "Failed to create company")}
                                </FormAlert>
                            )}
                            <Button type="submit" colorPalette="brand" alignSelf="flex-start" loading={createMutation.isPending}>
                                Create
                            </Button>
                        </Stack>
                    </form>
                </Card>
            )}

            <DataTable
                columns={columns}
                rows={companies}
                rowKey={(c) => c.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage="Failed to load companies"
                emptyMessage="No companies assigned to you yet"
            />

            {!isLoading && !isError && companies?.length === 0 && (
                <Text color="fg.muted" mt={4} fontSize="sm">
                    You don't have access to any companies yet. Ask an administrator to assign you a policy.
                </Text>
            )}

            <ConfirmDialog
                isOpen={deletingCompany !== null}
                title="Delete company"
                description={`Delete ${deletingCompany?.name}? This also deletes every balance sheet on file for it. This cannot be undone.`}
                confirmLabel="Delete"
                isLoading={deleteMutation.isPending}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeletingCompany(null)}
            />
        </PageContainer>
    );
};

export default CompaniesPage;
