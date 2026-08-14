import React, { useMemo, useState } from "react";
import { Badge, Button, HStack, Input, Text, Wrap } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import PageContainer from "../ui/PageContainer";
import DataTable, { type DataTableColumn } from "../ui/DataTable";
import ConfirmDialog from "../ui/ConfirmDialog";
import TableActionButton from "../ui/TableActionButton";
import { SEARCH_INPUT_PROPS } from "../ui/styles/inputStyles";
import { BRAND_SOLID_HOVER_PROPS } from "../ui/styles/buttonStyles";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import { toaster } from "../ui/toaster/toasterInstance";
import { usePoliciesQuery } from "./policyQueries";
import { useCreatePolicyMutation, useUpdatePolicyMutation, useDeletePolicyMutation } from "./policyMutations";
import PolicyFormDialog, { type PolicyFormValues } from "./PolicyFormDialog";
import PolicyStatsCard from "./PolicyStatsCard";
import type { PolicyRead } from "../api/policies_api";

/**
 * PoliciesPage
 * ----------------------------
 * Management CRUD for policies (backend: /authorization/policies). Route itself
 * is gated by ProtectedRoute permission="policies:read"; the create/edit/
 * delete affordances are additionally gated per-action here via IfCan,
 * since a caller might hold policies:read without policies:create/update/
 * delete.
 */
const PoliciesPage: React.FC = () => {
    const { t } = useTranslation(["policies", "ui_text"]);
    const { data: policies, isLoading, isError } = usePoliciesQuery();

    // Client-side, same reasoning as UsersPage's search: GET /policies
    // already loads the full list, so there's nothing to save by filtering
    // server-side, and filtering this small an in-memory array needs no
    // debounce.
    const [search, setSearch] = useState("");
    const filteredPolicies = useMemo(() => {
        if (!policies) return policies;
        const q = search.trim().toLowerCase();
        if (!q) return policies;
        return policies.filter(
            (p) => p.name.toLowerCase().includes(q) || p.resource_type.toLowerCase().includes(q)
        );
    }, [policies, search]);

    const [formOpen, setFormOpen] = useState(false);
    const [editingPolicy, setEditingPolicy] = useState<PolicyRead | undefined>(undefined);
    const [deletingPolicy, setDeletingPolicy] = useState<PolicyRead | null>(null);

    const createMutation = useCreatePolicyMutation();
    const updateMutation = useUpdatePolicyMutation();
    const deleteMutation = useDeletePolicyMutation();

    const openCreateForm = () => {
        setEditingPolicy(undefined);
        setFormOpen(true);
    };

    const openEditForm = (policy: PolicyRead) => {
        setEditingPolicy(policy);
        setFormOpen(true);
    };

    const closeForm = () => {
        setFormOpen(false);
        createMutation.reset();
        updateMutation.reset();
    };

    const handleFormSubmit = (values: PolicyFormValues) => {
        if (editingPolicy) {
            updateMutation.mutate(
                { policyName: editingPolicy.name, payload: values },
                {
                    onSuccess: () => {
                        toaster.create({ title: t("policies:page.policyUpdatedToast"), type: "success" });
                        closeForm();
                    },
                }
            );
        } else {
            createMutation.mutate(values, {
                onSuccess: () => {
                    toaster.create({ title: t("policies:page.policyCreatedToast"), type: "success" });
                    closeForm();
                },
            });
        }
    };

    const handleDeleteConfirm = () => {
        if (!deletingPolicy) return;
        deleteMutation.mutate(
            { policyName: deletingPolicy.name },
            {
                onSuccess: () => {
                    toaster.create({ title: t("policies:page.policyDeletedToast"), type: "success" });
                    setDeletingPolicy(null);
                },
                onError: (error) => {
                    toaster.create({ title: error.message, type: "error" });
                },
            }
        );
    };

    const columns: DataTableColumn<PolicyRead>[] = [
        {
            key: "name",
            header: t("policies:columns.name"),
            width: "220px",
            truncate: true,
            render: (p) => (
                <Text fontWeight="medium">
                    {p.name}
                    {!p.is_active && (
                        <Badge ml={2} colorPalette="gray" size="md">
                            {t("ui_text:inactive")}
                        </Badge>
                    )}
                </Text>
            ),
        },
        { key: "resource_type", header: t("policies:columns.resourceType"), width: "150px", truncate: true, render: (p) => p.resource_type },
        {
            key: "actions_list",
            header: t("policies:columns.actions"),
            render: (p) => (
                <Wrap gap={1}>
                    {p.actions.map((a) => (
                        <Badge key={a} colorPalette="brand" variant="subtle" fontSize="15px" px={2} py={0.5}>
                            {a}
                        </Badge>
                    ))}
                </Wrap>
            ),
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            // 150px only fit the English "Edit"/"Delete" labels; Hindi/Marathi
            // translations (e.g. "संपादित करें"/"काढून टाका") are noticeably
            // longer and got clipped by the table's fixed-width, overflow-hidden
            // cell. Widened and wrapped the same way usersColumns.tsx's own
            // row-actions column already handles multiple/longer buttons.
            width: "260px",
            render: (p) => (
                <HStack justify="flex-end" gap={2} wrap="wrap">
                    <IfCan action={PERMISSIONS.POLICIES_UPDATE}>
                        <TableActionButton colorPalette="orange" onClick={() => openEditForm(p)}>
                            {t("policies:columns.edit")}
                        </TableActionButton>
                    </IfCan>
                    <IfCan action={PERMISSIONS.POLICIES_DELETE}>
                        <TableActionButton colorPalette="red" onClick={() => setDeletingPolicy(p)}>
                            {t("ui_text:delete")}
                        </TableActionButton>
                    </IfCan>
                </HStack>
            ),
        },
    ];

    return (
        <PageContainer
            title={t("policies:page.title")}
            description={t("policies:page.description")}
            actions={<PolicyStatsCard policies={policies} isLoading={isLoading} />}
            headerExtra={
                <HStack gap={3} wrap="wrap">
                    <Input
                        placeholder={t("policies:page.searchPlaceholder")}
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        maxW="sm"
                        {...SEARCH_INPUT_PROPS}
                    />

                    <IfCan action={PERMISSIONS.POLICIES_CREATE}>
                        <Button colorPalette="brand" onClick={openCreateForm} {...BRAND_SOLID_HOVER_PROPS}>
                            {t("policies:page.createPolicy")}
                        </Button>
                    </IfCan>
                </HStack>
            }
        >
            <DataTable
                columns={columns}
                rows={filteredPolicies}
                rowKey={(p) => p.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage={t("policies:page.failedToLoadPolicies")}
                emptyMessage={search ? t("policies:page.noPoliciesMatchSearch") : t("policies:page.noPoliciesYet")}
                startIndex={0}
            />

            <PolicyFormDialog
                isOpen={formOpen}
                policy={editingPolicy}
                isSaving={createMutation.isPending || updateMutation.isPending}
                errorMessage={createMutation.error?.message ?? updateMutation.error?.message ?? null}
                onSubmit={handleFormSubmit}
                onClose={closeForm}
            />

            <ConfirmDialog
                isOpen={!!deletingPolicy}
                title={t("policies:page.deleteDialogTitle")}
                description={t("policies:page.deleteDialogDescription", { policyName: deletingPolicy?.name })}
                confirmLabel={t("ui_text:delete")}
                isLoading={deleteMutation.isPending}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeletingPolicy(null)}
            />
        </PageContainer>
    );
};

export default PoliciesPage;
