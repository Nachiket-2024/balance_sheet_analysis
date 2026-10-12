import { useState } from "react";
import { useTranslation } from "react-i18next";

import { usePageResetOn } from "../ui/hooks/usePageResetOn";
import { toaster } from "../ui/toaster/toasterInstance";
import { useAuthStore } from "../store/authStore";
import { useLanguageStore } from "../store/languageStore";
import { useUsersQuery, fetchAllMatchingUserEmails } from "./queries/userQueries";
import {
    useDeleteUserMutation,
    usePurgeUserMutation,
    useReactivateUserMutation,
    useUpdateUserRoleMutation,
    useExportUsersMutation,
} from "./queries/userMutations";
import type { ManagedUserRead } from "../api/users_api";
import { ALL_VALUE } from "./UsersFilterBar";
import { buildUsersColumns } from "./usersColumns";
import { useUsersPageFilters } from "./useUsersPageFilters";

const PAGE_SIZE = 25;

/** Maps the "All" placeholder option to `undefined` (no filter applied). */
function toBoolFilter(value: string): boolean | undefined {
    if (value === ALL_VALUE) return undefined;
    return value === "true";
}

/** Filter/sort/pagination/selection state and handlers for UsersPage, split
 * out so that file stays composition and JSX. Filter/sort state itself
 * lives in useUsersPageFilters.ts, see AGENTS.md's ~350-line target. */
export function useUsersPageState() {
    const { t } = useTranslation(["users", "ui_text"]);
    const {
        search,
        setSearch,
        debouncedSearch,
        role,
        setRole,
        verified,
        setVerified,
        status,
        setStatus,
        policy,
        setPolicy,
        permission,
        permissionSource,
        setPermission,
        lastLogin,
        setLastLogin,
        sort,
        toggleSort,
        hasActiveFilters,
        clearFilters,
    } = useUsersPageFilters();

    // A filter/sort change can make the current page number meaningless
    // (page 3 might not exist once filtered), so it resets to page 1. Also
    // reused below (with `page`) to key the selection reset, since a filter
    // change on page 1 wouldn't otherwise be detected.
    const filterResetKey = `${debouncedSearch}|${sort.key}|${sort.direction}|${role}|${verified}|${status}|${policy}|${permission}|${permissionSource}|${lastLogin}`;
    const [page, setPage] = usePageResetOn(filterResetKey);

    // Shared with handleExport and handleSelectAllMatching below: both need
    // the same server-side filters as the table itself, minus sort (neither
    // cares about row order).
    const activeFilters = {
        search: debouncedSearch,
        role: role || undefined,
        isVerified: toBoolFilter(verified),
        status: status || undefined,
        policy: policy || undefined,
        permission: permission || undefined,
        permissionSource,
        lastLogin: lastLogin || undefined,
    };

    const { data, isLoading, isFetching, isError } = useUsersQuery(page, PAGE_SIZE, {
        ...activeFilters,
        sortBy: sort.key || undefined,
        sortDir: sort.direction,
    });
    const users = data?.users;
    const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
    const currentUserEmail = useAuthStore((s) => s.email);
    // chromeLanguage, not pageLanguage - matches ActiveSessionsCard's own
    // last-seen column, since this is chrome (a management table), not
    // user-authored page content.
    const language = useLanguageStore((s) => s.chromeLanguage);

    const [deletingUser, setDeletingUser] = useState<ManagedUserRead | null>(null);
    const [purgingUser, setPurgingUser] = useState<ManagedUserRead | null>(null);
    const [pendingRoleChange, setPendingRoleChange] = useState<{ user: ManagedUserRead; role: string } | null>(null);
    // Stores the full row, not just the email: the dialog needs the role too,
    // to disable assign/revoke against the system account (same as usersColumns.tsx).
    // The backend rejects it anyway, but the dialog shouldn't offer a control
    // that can only ever fail. accessTab picks which of UserAccessDialog's
    // three tabs a row's icon (View/Policies/Permissions) jumps straight to.
    const [accessUser, setAccessUser] = useState<ManagedUserRead | null>(null);
    const [accessTab, setAccessTab] = useState<"details" | "policies" | "permissions">("details");

    // Bulk multi-select, keyed by user id. Reset whenever the page or filters
    // change so a stale selection can't silently span rows no longer on screen.
    const [selectedUserIds, setSelectedUserIds] = useState<Set<string | number>>(new Set());
    // "Select all N matching filters" (BulkActionToolbar), as opposed to
    // just the rows loaded on the current page: true once a permission holder commits
    // to it, with the emails snapshotted at that moment in
    // allMatchingEmails since selectedUserIds can only ever hold ids of
    // rows actually rendered.
    const [selectAllMatching, setSelectAllMatching] = useState(false);
    const [allMatchingEmails, setAllMatchingEmails] = useState<string[]>([]);
    const [isSelectingAllMatching, setIsSelectingAllMatching] = useState(false);
    const [bulkDialog, setBulkDialog] = useState<"policy" | "permission" | "role" | null>(null);
    // Off by default: clicking a row only selects it once the permission holder turns
    // this on, so normal text selection/copy still works otherwise.
    const [rowClickSelects, setRowClickSelects] = useState(false);

    // Clears selection on any page or filter change, so a bulk action can't
    // apply to users no longer on screen. Derived during render (not an
    // effect) to avoid an extra render.
    const selectionResetKey = `${page}|${filterResetKey}`;
    const [prevSelectionKey, setPrevSelectionKey] = useState(selectionResetKey);
    if (selectionResetKey !== prevSelectionKey) {
        setPrevSelectionKey(selectionResetKey);
        setSelectedUserIds(new Set());
        setSelectAllMatching(false);
    }

    const selectedUserEmails = selectAllMatching
        ? allMatchingEmails
        : (users ?? []).filter((u) => selectedUserIds.has(u.id)).map((u) => u.email);
    // Once "select all matching" is on, the count a permission holder sees/acts on is
    // the whole filtered set (data?.total), not just what's on screen.
    const selectedCount = selectAllMatching ? (data?.total ?? allMatchingEmails.length) : selectedUserIds.size;

    const clearSelection = () => {
        setSelectedUserIds(new Set());
        setSelectAllMatching(false);
    };

    // Any manual checkbox change (row or header "select all") drops back to
    // page-level selection - otherwise unchecking a row while "select all
    // matching" is active would silently do nothing, since selectedUserEmails
    // ignores selectedUserIds entirely in that mode.
    const handleSelectionChange: typeof setSelectedUserIds = (update) => {
        setSelectAllMatching(false);
        setSelectedUserIds(update);
    };

    const handleSelectAllMatching = async () => {
        setIsSelectingAllMatching(true);
        try {
            const emails = await fetchAllMatchingUserEmails(activeFilters);
            setAllMatchingEmails(emails);
            setSelectAllMatching(true);
        } catch (error) {
            toaster.create({
                title: error instanceof Error ? error.message : t("users:page.selectAllMatchingFailed"),
                type: "error",
            });
        } finally {
            setIsSelectingAllMatching(false);
        }
    };

    const deleteMutation = useDeleteUserMutation();
    const purgeMutation = usePurgeUserMutation();
    const reactivateMutation = useReactivateUserMutation();
    const roleMutation = useUpdateUserRoleMutation();
    const exportMutation = useExportUsersMutation();

    const handleExport = () => {
        exportMutation.mutate(activeFilters, { onError: (error) => toaster.create({ title: error.message, type: "error" }) });
    };

    const handleRoleChangeConfirm = () => {
        if (!pendingRoleChange) return;
        const { user, role: newRole } = pendingRoleChange;
        roleMutation.mutate(
            { userEmail: user.email, role: newRole },
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
                    toaster.create({ title: t("users:page.userDeactivatedToast"), type: "success" });
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
                    toaster.create({ title: t("users:page.userDeletedToast"), type: "success" });
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
        language,
        currentUserEmail,
        onRoleChangeRequest: (user, newRole) => setPendingRoleChange({ user, role: newRole }),
        onOpenAccess: (user, tab) => {
            setAccessTab(tab);
            setAccessUser(user);
        },
        onReactivate: handleReactivate,
        reactivatingEmail: reactivateMutation.isPending ? reactivateMutation.variables?.userEmail : undefined,
        onPurgeRequest: setPurgingUser,
        onDeleteRequest: setDeletingUser,
    });

    return {
        search,
        setSearch,
        role,
        setRole,
        verified,
        setVerified,
        status,
        setStatus,
        policy,
        setPolicy,
        permission,
        permissionSource,
        setPermission,
        lastLogin,
        setLastLogin,
        sort,
        toggleSort,
        page,
        setPage,
        totalPages,
        users,
        // Distinct from isLoading (true only on the very first, empty-cache
        // fetch): this covers every refetch, including the ones a search
        // keystroke or filter change triggers, since useUsersQuery keeps the
        // previous page's rows on screen (placeholderData: keepPreviousData)
        // while that happens rather than clearing to a loading state.
        isFetching,
        totalResults: data?.total,
        isLoading,
        isError,
        columns,
        deletingUser,
        setDeletingUser,
        purgingUser,
        setPurgingUser,
        pendingRoleChange,
        setPendingRoleChange,
        accessUser,
        setAccessUser,
        accessTab,
        selectedUserIds,
        setSelectedUserIds,
        handleSelectionChange,
        selectedUserEmails,
        selectedCount,
        selectAllMatching,
        isSelectingAllMatching,
        handleSelectAllMatching,
        clearSelection,
        hasActiveFilters,
        clearFilters,
        bulkDialog,
        setBulkDialog,
        rowClickSelects,
        setRowClickSelects,
        deleteMutation,
        purgeMutation,
        roleMutation,
        exportMutation,
        handleExport,
        handleRoleChangeConfirm,
        handleDeleteConfirm,
        handlePurgeConfirm,
        PAGE_SIZE,
    };
}
