import React, { useState } from "react";
import { Badge, Button, HStack, NativeSelect, Text } from "@chakra-ui/react";

import PageContainer from "../ui/PageContainer";
import DataTable, { type DataTableColumn } from "../ui/DataTable";
import ConfirmDialog from "../ui/ConfirmDialog";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import { toaster } from "../ui/toasterInstance";
import { useAuthStore } from "../store/authStore";
import { useUsersQuery } from "./userQueries";
import {
    useDeleteUserMutation,
    usePurgeUserMutation,
    useReactivateUserMutation,
    useUpdateUserRoleMutation,
} from "./userMutations";
import type { AdminUserRead } from "../api/users_api";
import UserPoliciesDialog from "./UserPoliciesDialog";

const ROLE_OPTIONS = ["user", "admin", "system"] as const;

/**
 * UsersPage
 * ----------------------------
 * Admin list of every user (backend: GET /users/), with per-row role
 * change, delete, and a "Policies" dialog for assigning/
 * revoking individual policy grants. Route is gated by
 * ProtectedRoute permission="users:list_all"; each destructive/privileged
 * action is additionally gated per-action via IfCan.
 */
const UsersPage: React.FC = () => {
    const { data: users, isLoading, isError } = useUsersQuery();
    const currentUserEmail = useAuthStore((s) => s.email);

    const [deletingUser, setDeletingUser] = useState<AdminUserRead | null>(null);
    const [purgingUser, setPurgingUser] = useState<AdminUserRead | null>(null);
    const [pendingRoleChange, setPendingRoleChange] = useState<{ user: AdminUserRead; role: string } | null>(null);
    const [policiesUserEmail, setPoliciesUserEmail] = useState<string | null>(null);

    const deleteMutation = useDeleteUserMutation();
    const purgeMutation = usePurgeUserMutation();
    const reactivateMutation = useReactivateUserMutation();
    const roleMutation = useUpdateUserRoleMutation();

    const handleRoleChangeConfirm = () => {
        if (!pendingRoleChange) return;
        const { user, role } = pendingRoleChange;
        roleMutation.mutate(
            { userEmail: user.email, role },
            {
                onSuccess: () => {
                    toaster.create({ title: "Role updated", type: "success" });
                    setPendingRoleChange(null);
                },
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    const handleDeleteConfirm = () => {
        if (!deletingUser) return;
        deleteMutation.mutate(
            { userEmail: deletingUser.email },
            {
                onSuccess: () => {
                    toaster.create({ title: "User deleted : this is reversible via Reactivate", type: "success" });
                    setDeletingUser(null);
                },
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    const handlePurgeConfirm = () => {
        if (!purgingUser) return;
        purgeMutation.mutate(
            { userEmail: purgingUser.email },
            {
                onSuccess: () => {
                    toaster.create({ title: "User permanently removed", type: "success" });
                    setPurgingUser(null);
                },
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    const handleReactivate = (userEmail: string) => {
        reactivateMutation.mutate(
            { userEmail },
            {
                onSuccess: () => toaster.create({ title: "User reactivated", type: "success" }),
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    const columns: DataTableColumn<AdminUserRead>[] = [
        {
            key: "name",
            header: "Name",
            render: (u) => (
                <Text fontWeight="medium">
                    {u.name}
                    {u.email === currentUserEmail && (
                        <Badge ml={2} colorPalette="brand" variant="subtle">
                            You
                        </Badge>
                    )}
                </Text>
            ),
        },
        { key: "email", header: "Email", render: (u) => u.email },
        {
            key: "role",
            header: "Role",
            render: (u) => (
                <IfCan
                    action={PERMISSIONS.USERS_ASSIGN_ROLE}
                    fallback={<Text textTransform="capitalize">{u.role ?? ":"}</Text>}
                >
                    <NativeSelect.Root
                        size="sm"
                        w="130px"
                        disabled={u.email === currentUserEmail}
                        title={u.email === currentUserEmail ? "You cannot change your own role" : undefined}
                    >
                        <NativeSelect.Field
                            value={u.role ?? ""}
                            onChange={(e) => setPendingRoleChange({ user: u, role: e.target.value })}
                            aria-label={`Change role for ${u.email}`}
                        >
                            {ROLE_OPTIONS.map((role) => (
                                <option key={role} value={role}>
                                    {role}
                                </option>
                            ))}
                        </NativeSelect.Field>
                        <NativeSelect.Indicator />
                    </NativeSelect.Root>
                </IfCan>
            ),
        },
        {
            key: "status",
            header: "Status",
            render: (u) => (
                <HStack gap={1}>
                    <Badge colorPalette={u.is_verified ? "green" : "yellow"}>
                        {u.is_verified ? "Verified" : "Unverified"}
                    </Badge>
                    {u.deleted_at ? (
                        <Badge colorPalette="red">Deleted</Badge>
                    ) : (
                        !u.is_active && <Badge colorPalette="red">Inactive</Badge>
                    )}
                </HStack>
            ),
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            render: (u) => (
                <HStack justify="flex-end" gap={2}>
                    <IfCan action={PERMISSIONS.POLICIES_READ}>
                        <Button size="xs" variant="outline" onClick={() => setPoliciesUserEmail(u.email)}>
                            Policies
                        </Button>
                    </IfCan>
                    {u.deleted_at ? (
                        <>
                            <IfCan action={PERMISSIONS.USERS_REACTIVATE}>
                                <Button
                                    size="xs"
                                    variant="outline"
                                    colorPalette="green"
                                    onClick={() => handleReactivate(u.email)}
                                    loading={reactivateMutation.isPending && reactivateMutation.variables?.userEmail === u.email}
                                >
                                    Reactivate
                                </Button>
                            </IfCan>
                            <IfCan action={PERMISSIONS.USERS_PURGE}>
                                <Button
                                    size="xs"
                                    variant="outline"
                                    colorPalette="red"
                                    onClick={() => setPurgingUser(u)}
                                    disabled={u.email === currentUserEmail}
                                >
                                    Purge
                                </Button>
                            </IfCan>
                        </>
                    ) : (
                        <IfCan action={PERMISSIONS.USERS_DELETE_ANY}>
                            <Button
                                size="xs"
                                variant="outline"
                                colorPalette="red"
                                onClick={() => setDeletingUser(u)}
                                disabled={u.email === currentUserEmail}
                            >
                                Delete
                            </Button>
                        </IfCan>
                    )}
                </HStack>
            ),
        },
    ];

    return (
        <PageContainer title="Users" description="Manage user accounts, roles, and policy assignments.">
            <DataTable
                columns={columns}
                rows={users}
                rowKey={(u) => u.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage="Failed to load users"
                emptyMessage="No users found"
            />

            <UserPoliciesDialog
                isOpen={!!policiesUserEmail}
                userEmail={policiesUserEmail}
                onClose={() => setPoliciesUserEmail(null)}
            />

            <ConfirmDialog
                isOpen={!!deletingUser}
                title="Delete user"
                description={`Delete "${deletingUser?.email}"? This deactivates their account and ends every active session : it's reversible via Reactivate.`}
                confirmLabel="Delete"
                isLoading={deleteMutation.isPending}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeletingUser(null)}
            />

            <ConfirmDialog
                isOpen={!!purgingUser}
                title="Permanently remove user"
                description={`Permanently remove "${purgingUser?.email}"? This cannot be undone : the account, its policy assignments, and its ability to ever be reactivated are all gone. (Authorization/security audit history is preserved separately.)`}
                confirmLabel="Permanently remove"
                isLoading={purgeMutation.isPending}
                onConfirm={handlePurgeConfirm}
                onCancel={() => setPurgingUser(null)}
            />

            <ConfirmDialog
                isOpen={!!pendingRoleChange}
                title="Change role"
                description={`Change ${pendingRoleChange?.user.email}'s role to "${pendingRoleChange?.role}"? Role is display/grouping metadata only : this does not itself change what they're permitted to do.`}
                confirmLabel="Change role"
                isDestructive={false}
                isLoading={roleMutation.isPending}
                onConfirm={handleRoleChangeConfirm}
                onCancel={() => setPendingRoleChange(null)}
            />
        </PageContainer>
    );
};

export default UsersPage;
