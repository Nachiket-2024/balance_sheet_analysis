import React, { useState } from "react";
import { HStack, Input, Stack } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import PageContainer from "../ui/PageContainer";
import DataTable from "../ui/DataTable";
import ConfirmDialog from "../ui/ConfirmDialog";
import Pagination from "../ui/Pagination";
import StyledSelect from "../ui/StyledSelect";
import { SEARCH_INPUT_PROPS } from "../ui/styles/inputStyles";
import { useDebouncedValue } from "../ui/hooks/useDebouncedValue";
import { useSortState } from "../ui/hooks/useSortState";
import { usePageResetOn } from "../ui/hooks/usePageResetOn";
import { toaster } from "../ui/toaster/toasterInstance";
import { useAuthStore } from "../store/authStore";
import { useUsersQuery } from "./userQueries";
import UserStatsCard from "./UserStatsCard";
import {
    useDeleteUserMutation,
    usePurgeUserMutation,
    useReactivateUserMutation,
    useUpdateUserRoleMutation,
} from "./userMutations";
import type { ManagedUserRead } from "../api/users_api";
import UserPoliciesDialog from "./UserPoliciesDialog";
import UserDetailsDialog from "./UserDetailsDialog";
import { ROLE_OPTIONS, capitalize, buildUsersColumns } from "./usersColumns";

const PAGE_SIZE = 25;
const ALL_VALUE = "";

/** "" (a placeholder "All" option) maps to `undefined` (no filter applied). */
function toBoolFilter(value: string): boolean | undefined {
    if (value === ALL_VALUE) return undefined;
    return value === "true";
}

/**
 * UsersPage
 * ----------------------------
 * Management list of every user (backend: GET /users/), with per-row role
 * change, delete, and a "Policies" dialog for assigning/
 * revoking individual policy grants. Route is gated by
 * ProtectedRoute permission="users:list_all"; each destructive/privileged
 * action is additionally gated per-action via IfCan. Name/Email/Role sort
 * server-side (click the header), and Role/Verified/Status filter
 * server-side too - both narrow the whole result set, not just the
 * currently-loaded page, same as the audit_log/ section components (both
 * share ui/hooks/usePageResetOn.ts for the page-reset-on-filter-change logic).
 */
const UsersPage: React.FC = () => {
    const { t } = useTranslation(["users", "ui_text"]);
    const [search, setSearch] = useState("");
    // Debounced, not the raw keystroke value: search is now a real request
    // (server-side, since the table itself is paginated and no longer holds
    // every user to filter client-side), so typing shouldn't fire one
    // request per character.
    const debouncedSearch = useDebouncedValue(search);

    // No default sort column: the table's natural order (insertion/id order)
    // isn't shown as its own column, so nothing should read as "actively
    // sorted" until a header is actually clicked.
    const { sort, toggleSort } = useSortState("");
    const [role, setRole] = useState(ALL_VALUE);
    const [verified, setVerified] = useState(ALL_VALUE);
    const [status, setStatus] = useState(ALL_VALUE);

    // A search/filter/sort change that changes the result set makes whatever
    // page you were on potentially meaningless (e.g. page 3 of an unfiltered
    // list may not exist at all once filtered) - always back to page 1 for a
    // fresh query. See usePageResetOn's own docstring for why this is state
    // derived during render, not an effect.
    const [page, setPage] = usePageResetOn(`${debouncedSearch}|${sort.key}|${sort.direction}|${role}|${verified}|${status}`);

    const { data, isLoading, isError } = useUsersQuery(page, PAGE_SIZE, {
        search: debouncedSearch,
        role: role || undefined,
        isVerified: toBoolFilter(verified),
        status: status || undefined,
        sortBy: sort.key || undefined,
        sortDir: sort.direction,
    });
    const users = data?.users;
    const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
    const currentUserEmail = useAuthStore((s) => s.email);

    const [deletingUser, setDeletingUser] = useState<ManagedUserRead | null>(null);
    const [purgingUser, setPurgingUser] = useState<ManagedUserRead | null>(null);
    const [pendingRoleChange, setPendingRoleChange] = useState<{ user: ManagedUserRead; role: string } | null>(null);
    const [policiesUserEmail, setPoliciesUserEmail] = useState<string | null>(null);
    const [viewingUser, setViewingUser] = useState<ManagedUserRead | null>(null);

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
                    toaster.create({ title: t("users:page.roleUpdatedToast"), type: "success" });
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
                    toaster.create({ title: t("users:page.userDeletedToast"), type: "success" });
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
                    toaster.create({ title: t("users:page.userPurgedToast"), type: "success" });
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
                onSuccess: () => toaster.create({ title: t("users:page.userReactivatedToast"), type: "success" }),
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    const columns = buildUsersColumns({
        t,
        currentUserEmail,
        onRoleChangeRequest: (user, role) => setPendingRoleChange({ user, role }),
        onView: setViewingUser,
        onPolicies: setPoliciesUserEmail,
        onReactivate: handleReactivate,
        reactivatingEmail: reactivateMutation.isPending ? reactivateMutation.variables?.userEmail : undefined,
        onPurgeRequest: setPurgingUser,
        onDeleteRequest: setDeletingUser,
    });

    return (
        <PageContainer
            title={t("users:page.title")}
            description={t("users:page.description")}
            actions={
                <UserStatsCard
                    onFilterTotal={() => {
                        setSearch("");
                        setRole(ALL_VALUE);
                        setVerified(ALL_VALUE);
                        setStatus(ALL_VALUE);
                    }}
                    onFilterVerified={() => {
                        setSearch("");
                        setVerified("true");
                        setRole(ALL_VALUE);
                        setStatus(ALL_VALUE);
                    }}
                    onFilterUnverified={() => {
                        setSearch("");
                        setVerified("false");
                        setRole(ALL_VALUE);
                        setStatus(ALL_VALUE);
                    }}
                    onFilterInactive={() => {
                        setSearch("");
                        setStatus("inactive");
                        setRole(ALL_VALUE);
                        setVerified(ALL_VALUE);
                    }}
                />
            }
            headerExtra={
                <Stack gap={3}>
                    <Input
                        placeholder={t("users:page.searchPlaceholder")}
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        maxW="sm"
                        {...SEARCH_INPUT_PROPS}
                    />

                    <HStack gap={3} wrap="wrap">
                        <StyledSelect
                            w="140px"
                            ariaLabel={t("users:page.filterByRole")}
                            value={role}
                            onChange={setRole}
                            textTransform="capitalize"
                            options={[
                                { value: ALL_VALUE, label: t("users:page.allRoles") },
                                ...ROLE_OPTIONS.map((value) => ({ value, label: capitalize(value) })),
                            ]}
                        />

                        <StyledSelect
                            w="150px"
                            ariaLabel={t("users:page.filterByVerified")}
                            value={verified}
                            onChange={setVerified}
                            options={[
                                { value: ALL_VALUE, label: t("users:page.allVerification") },
                                { value: "true", label: t("users:page.verified") },
                                { value: "false", label: t("users:page.unverified") },
                            ]}
                        />

                        <StyledSelect
                            w="140px"
                            ariaLabel={t("users:page.filterByStatus")}
                            value={status}
                            onChange={setStatus}
                            options={[
                                { value: ALL_VALUE, label: t("users:page.allStatuses") },
                                { value: "active", label: t("ui_text:active") },
                                { value: "inactive", label: t("ui_text:inactive") },
                                { value: "deleted", label: t("users:page.deleted") },
                            ]}
                        />
                    </HStack>
                </Stack>
            }
        >
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mb={4} />

            <DataTable
                columns={columns}
                rows={users}
                rowKey={(u) => u.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage={t("users:page.failedToLoadUsers")}
                emptyMessage={search ? t("users:page.noUsersMatchSearch") : t("users:page.noUsersMatchFilters")}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />

            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mt={4} />

            <UserPoliciesDialog
                isOpen={!!policiesUserEmail}
                userEmail={policiesUserEmail}
                onClose={() => setPoliciesUserEmail(null)}
            />

            <UserDetailsDialog
                isOpen={!!viewingUser}
                user={viewingUser}
                onClose={() => setViewingUser(null)}
            />

            <ConfirmDialog
                isOpen={!!deletingUser}
                title={t("users:page.deleteDialogTitle")}
                description={t("users:page.deleteDialogDescription", { email: deletingUser?.email })}
                confirmLabel={t("ui_text:delete")}
                isLoading={deleteMutation.isPending}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeletingUser(null)}
            />

            <ConfirmDialog
                isOpen={!!purgingUser}
                title={t("users:page.purgeDialogTitle")}
                description={t("users:page.purgeDialogDescription", { email: purgingUser?.email })}
                confirmLabel={t("users:page.purgeConfirmLabel")}
                isLoading={purgeMutation.isPending}
                onConfirm={handlePurgeConfirm}
                onCancel={() => setPurgingUser(null)}
            />

            <ConfirmDialog
                isOpen={!!pendingRoleChange}
                title={t("users:page.changeRoleDialogTitle")}
                description={t("users:page.changeRoleDialogDescription", {
                    email: pendingRoleChange?.user.email,
                    role: pendingRoleChange ? capitalize(pendingRoleChange.role) : "",
                })}
                confirmLabel={t("users:page.changeRoleConfirmLabel")}
                isDestructive={false}
                isLoading={roleMutation.isPending}
                onConfirm={handleRoleChangeConfirm}
                onCancel={() => setPendingRoleChange(null)}
            />
        </PageContainer>
    );
};

export default UsersPage;
