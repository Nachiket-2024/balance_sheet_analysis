import React from "react";
import { Download, Users, UsersRound } from "lucide-react";
import { useTranslation } from "react-i18next";

import PageContainer from "../ui/navigation/PageContainer";
import GlossaryHelp from "../ui/display/GlossaryHelp";
import DataTable from "../ui/DataTable/DataTable";
import Pagination from "../ui/navigation/Pagination";
import { Button } from "../ui/buttons/Button";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import UserStatsCard, { type UserStatTileKey } from "./UserStatsCard";
import UsersFilterBar, { ALL_VALUE } from "./UsersFilterBar";
import UsersPageDialogs from "./dialogs/UsersPageDialogs";
import BulkActionToolbar from "./bulk/BulkActionToolbar";
import BulkUserAccessDialog from "./bulk/BulkUserAccessDialog";
import { useUsersPageState } from "./useUsersPageState";

/**
 * UsersPage
 * ----------------------------
 * Management list of every user (backend: GET /users/), with per-row role
 * change, delete, and a "Policies" dialog for assigning/revoking individual
 * policy grants. Route is gated by ProtectedRoute permission="users:list_all";
 * each destructive/privileged action is additionally gated via IfCan.
 * Name/Email/Role sort and Role/Verified/Status/Policy/Permission filter
 * both happen server-side, narrowing the whole result set rather than just
 * the loaded page (same as audit_log/, sharing its
 * ui/hooks/usePageResetOn.ts for resetting to page 1 on filter change).
 * The filter controls live in UsersFilterBar.tsx, every dialog this page
 * can open lives in UsersPageDialogs.tsx, and the query/mutation/handler
 * wiring lives in useUsersPageState.ts; this file just composes the three.
 */
const UsersPage: React.FC = () => {
    const { t } = useTranslation(["users", "ui_text"]);
    const {
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
        isFetching,
        totalResults,
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
        handleSelectionChange,
        selectedUserEmails,
        selectedCount,
        selectAllMatching,
        isSelectingAllMatching,
        handleSelectAllMatching,
        clearSelection,
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
    } = useUsersPageState();

    // Drives UserStatsCard's pressed tile: only "on" when the filter state
    // exactly matches what that tile's own click handler sets below, so a
    // tile never looks pressed just because its number happens to agree
    // with an unrelated combination of filters (design/users.html's
    // `.tile[aria-pressed="true"]`).
    const activeTile: UserStatTileKey | null = search || role !== ALL_VALUE || policy !== ALL_VALUE
        || permission !== ALL_VALUE || lastLogin !== ALL_VALUE
        ? null
        : verified === "true" && status === ALL_VALUE
          ? "verified"
          : verified === "false" && status === ALL_VALUE
            ? "unverified"
            : status === "deleted" && verified === ALL_VALUE
              ? "inactive"
              : verified === ALL_VALUE && status === ALL_VALUE
                ? "total"
                : null;

    return (
        <PageContainer
            title={t("users:page.title")}
            icon={Users}
            titleExtra={
                <GlossaryHelp
                    ariaLabel={t("users:page.glossaryAriaLabel")}
                    items={[
                        { term: t("users:page.glossary.role.term"), definition: t("users:page.glossary.role.definition") },
                        { term: t("users:page.glossary.verified.term"), definition: t("users:page.glossary.verified.definition") },
                        { term: t("users:page.glossary.policy.term"), definition: t("users:page.glossary.policy.definition") },
                        { term: t("users:page.glossary.permission.term"), definition: t("users:page.glossary.permission.definition") },
                        { term: t("users:page.glossary.deactivated.term"), definition: t("users:page.glossary.deactivated.definition") },
                    ]}
                />
            }
            description={t("users:page.description")}
            actions={
                // Top-right of the page header, next to the title
                // (design/users.html's #exportBtn) - its own dedicated
                // slot instead of a sibling in the search row, so it can
                // never get pushed out of view by the filter row wrapping.
                <IfCan action={PERMISSIONS.USERS_LIST_ALL}>
                    <Button size="sm" variant="brand-tinted-outline" onClick={handleExport} loading={exportMutation.isPending}>
                        <Download size={16} />
                        {t("users:page.exportCsv")}
                    </Button>
                </IfCan>
            }
            headerExtra={
                // Stats row above the filter bar, both full width (design/
                // users.html: "Stat tiles are one short row under the
                // title, so the filters get the full width instead of
                // wrapping beside a tall stats card") - rendered here, not
                // PageContainer's narrow `actions` slot.
                <div className="flex flex-col gap-4">
                    <UserStatsCard
                        activeTile={activeTile}
                        onFilterTotal={() => {
                            setSearch("");
                            setRole(ALL_VALUE);
                            setVerified(ALL_VALUE);
                            setStatus(ALL_VALUE);
                            setPolicy(ALL_VALUE);
                            setPermission(ALL_VALUE);
                            setLastLogin(ALL_VALUE);
                        }}
                        onFilterVerified={() => {
                            setSearch("");
                            setVerified("true");
                            setRole(ALL_VALUE);
                            setStatus(ALL_VALUE);
                            setPolicy(ALL_VALUE);
                            setPermission(ALL_VALUE);
                            setLastLogin(ALL_VALUE);
                        }}
                        onFilterUnverified={() => {
                            setSearch("");
                            setVerified("false");
                            setRole(ALL_VALUE);
                            setStatus(ALL_VALUE);
                            setPolicy(ALL_VALUE);
                            setPermission(ALL_VALUE);
                            setLastLogin(ALL_VALUE);
                        }}
                        onFilterInactive={() => {
                            setSearch("");
                            setStatus("deleted");
                            setRole(ALL_VALUE);
                            setVerified(ALL_VALUE);
                            setPolicy(ALL_VALUE);
                            setPermission(ALL_VALUE);
                            setLastLogin(ALL_VALUE);
                        }}
                    />
                    <UsersFilterBar
                        search={search}
                        setSearch={setSearch}
                        isFetching={isFetching}
                        totalResults={totalResults}
                        role={role}
                        setRole={setRole}
                        verified={verified}
                        setVerified={setVerified}
                        status={status}
                        setStatus={setStatus}
                        policy={policy}
                        setPolicy={setPolicy}
                        permission={permission}
                        setPermission={setPermission}
                        permissionSource={permissionSource}
                        lastLogin={lastLogin}
                        setLastLogin={setLastLogin}
                        onClearFilters={clearFilters}
                    />
                </div>
            }
        >
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} className="mb-4" />

            <BulkActionToolbar
                selectedCount={selectedCount}
                onBulkAssignPolicy={() => setBulkDialog("policy")}
                onBulkGrantPermission={() => setBulkDialog("permission")}
                onBulkSetRole={() => setBulkDialog("role")}
                onClearSelection={clearSelection}
                rowClickSelects={rowClickSelects}
                onToggleRowClickSelects={() => setRowClickSelects((v) => !v)}
                pageSelectedCount={selectedUserIds.size}
                pageRowCount={users?.length ?? 0}
                totalMatching={totalResults ?? 0}
                selectAllMatching={selectAllMatching}
                onSelectAllMatching={handleSelectAllMatching}
                isSelectingAllMatching={isSelectingAllMatching}
            />

            <DataTable
                columns={columns}
                rows={users}
                rowKey={(u) => u.id}
                isLoading={isLoading}
                isError={isError}
                isFetching={isFetching}
                errorMessage={t("users:page.failedToLoadUsers")}
                emptyMessage={search ? t("users:page.noUsersMatchSearch") : t("users:page.noUsersMatchFilters")}
                emptyIcon={<UsersRound size={32} aria-hidden="true" />}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
                rowClickSelects={rowClickSelects}
                selectable
                selectedKeys={selectedUserIds}
                onSelectionChange={handleSelectionChange}
            />

            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} className="mt-4" />

            <BulkUserAccessDialog
                isOpen={bulkDialog !== null}
                userEmails={selectedUserEmails}
                initialTab={bulkDialog === "permission" ? "permissions" : bulkDialog === "role" ? "roles" : "policies"}
                onClose={() => setBulkDialog(null)}
            />

            <UsersPageDialogs
                accessUser={accessUser}
                accessTab={accessTab}
                onCloseAccess={() => setAccessUser(null)}
                deletingUser={deletingUser}
                isDeletePending={deleteMutation.isPending}
                onConfirmDelete={handleDeleteConfirm}
                onCancelDelete={() => setDeletingUser(null)}
                purgingUser={purgingUser}
                isPurgePending={purgeMutation.isPending}
                onConfirmPurge={handlePurgeConfirm}
                onCancelPurge={() => setPurgingUser(null)}
                pendingRoleChange={pendingRoleChange}
                isRoleChangePending={roleMutation.isPending}
                onConfirmRoleChange={handleRoleChangeConfirm}
                onCancelRoleChange={() => setPendingRoleChange(null)}
            />
        </PageContainer>
    );
};

export default UsersPage;
