import React, { useState } from "react";
import { Badge, Button, HStack, Text, Wrap } from "@chakra-ui/react";

import PageContainer from "../ui/PageContainer";
import DataTable, { type DataTableColumn } from "../ui/DataTable";
import ConfirmDialog from "../ui/ConfirmDialog";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import { toaster } from "../ui/toasterInstance";
import { usePoliciesQuery } from "./policyQueries";
import { useCreatePolicyMutation, useUpdatePolicyMutation, useDeletePolicyMutation } from "./policyMutations";
import PolicyFormDialog, { type PolicyFormValues } from "./PolicyFormDialog";
import type { PolicyRead } from "../api/policies_api";

/**
 * PoliciesPage
 * ----------------------------
 * Admin CRUD for policies (backend: /authorization/policies). Route itself
 * is gated by ProtectedRoute permission="policies:read"; the create/edit/
 * delete affordances are additionally gated per-action here via IfCan,
 * since a caller might hold policies:read without policies:create/update/
 * delete.
 */
const PoliciesPage: React.FC = () => {
    const { data: policies, isLoading, isError } = usePoliciesQuery();

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
                        toaster.create({ title: "Policy updated", type: "success" });
                        closeForm();
                    },
                }
            );
        } else {
            createMutation.mutate(values, {
                onSuccess: () => {
                    toaster.create({ title: "Policy created", type: "success" });
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
                    toaster.create({ title: "Policy deleted", type: "success" });
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
            header: "Name",
            render: (p) => (
                <Text fontWeight="medium">
                    {p.name}
                    {!p.is_active && (
                        <Badge ml={2} colorPalette="gray">
                            Inactive
                        </Badge>
                    )}
                </Text>
            ),
        },
        { key: "resource_type", header: "Resource type", render: (p) => p.resource_type },
        {
            key: "actions_list",
            header: "Actions",
            render: (p) => (
                <Wrap gap={1}>
                    {p.actions.map((a) => (
                        <Badge key={a} colorPalette="brand" variant="subtle">
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
            render: (p) => (
                <HStack justify="flex-end" gap={2}>
                    <IfCan action={PERMISSIONS.POLICIES_UPDATE}>
                        <Button size="xs" variant="outline" onClick={() => openEditForm(p)}>
                            Edit
                        </Button>
                    </IfCan>
                    <IfCan action={PERMISSIONS.POLICIES_DELETE}>
                        <Button size="xs" variant="outline" colorPalette="red" onClick={() => setDeletingPolicy(p)}>
                            Delete
                        </Button>
                    </IfCan>
                </HStack>
            ),
        },
    ];

    return (
        <PageContainer
            title="Policies"
            description="Define and manage the access-control policies that grant permissions to users."
            actions={
                <IfCan action={PERMISSIONS.POLICIES_CREATE}>
                    <Button colorPalette="brand" onClick={openCreateForm}>
                        Create Policy
                    </Button>
                </IfCan>
            }
        >
            <DataTable
                columns={columns}
                rows={policies}
                rowKey={(p) => p.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage="Failed to load policies"
                emptyMessage="No policies yet : create one to start granting permissions."
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
                title="Delete policy"
                description={`Delete "${deletingPolicy?.name}"? Any user assigned this policy will immediately lose the permissions it grants.`}
                confirmLabel="Delete"
                isLoading={deleteMutation.isPending}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeletingPolicy(null)}
            />
        </PageContainer>
    );
};

export default PoliciesPage;
