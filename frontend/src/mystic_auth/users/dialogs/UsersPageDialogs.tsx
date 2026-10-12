import React from "react";
import { useTranslation } from "react-i18next";

import ConfirmDialog from "../../ui/feedback/ConfirmDialog";
import type { ManagedUserRead } from "../../api/users_api";
import UserAccessDialog from "./UserAccessDialog";
import { capitalize } from "../usersColumns";

interface PendingRoleChange {
    user: ManagedUserRead;
    role: string;
}

interface UsersPageDialogsProps {
    accessUser: ManagedUserRead | null;
    accessTab: "details" | "policies" | "permissions";
    onCloseAccess: () => void;
    deletingUser: ManagedUserRead | null;
    isDeletePending: boolean;
    onConfirmDelete: () => void;
    onCancelDelete: () => void;
    purgingUser: ManagedUserRead | null;
    isPurgePending: boolean;
    onConfirmPurge: () => void;
    onCancelPurge: () => void;
    pendingRoleChange: PendingRoleChange | null;
    isRoleChangePending: boolean;
    onConfirmRoleChange: () => void;
    onCancelRoleChange: () => void;
}

/** Every dialog UsersPage can open: the Policies/Details inspection dialogs,
 * plus a ConfirmDialog each for delete/purge/role-change. Split out of
 * UsersPage.tsx, which still owns all the state (which user, which
 * mutation) - this component just renders it. */
const UsersPageDialogs: React.FC<UsersPageDialogsProps> = ({
    accessUser,
    accessTab,
    onCloseAccess,
    deletingUser,
    isDeletePending,
    onConfirmDelete,
    onCancelDelete,
    purgingUser,
    isPurgePending,
    onConfirmPurge,
    onCancelPurge,
    pendingRoleChange,
    isRoleChangePending,
    onConfirmRoleChange,
    onCancelRoleChange,
}) => {
    const { t } = useTranslation(["users", "ui_text"]);

    return (
        <>
            <UserAccessDialog
                isOpen={!!accessUser}
                user={accessUser}
                initialTab={accessTab}
                isSystemUser={accessUser?.role === "system"}
                onClose={onCloseAccess}
            />

            <ConfirmDialog
                isOpen={!!deletingUser}
                title={t("users:page.deactivateDialogTitle")}
                description={t("users:page.deactivateDialogDescription", { email: deletingUser?.email })}
                confirmLabel={t("users:columns.deactivate")}
                isLoading={isDeletePending}
                onConfirm={onConfirmDelete}
                onCancel={onCancelDelete}
            />

            <ConfirmDialog
                isOpen={!!purgingUser}
                title={t("users:page.deleteDialogTitle")}
                description={t("users:page.deleteDialogDescription", { email: purgingUser?.email })}
                confirmLabel={t("ui_text:delete")}
                isLoading={isPurgePending}
                onConfirm={onConfirmPurge}
                onCancel={onCancelPurge}
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
                isLoading={isRoleChangePending}
                onConfirm={onConfirmRoleChange}
                onCancel={onCancelRoleChange}
            />
        </>
    );
};

export default UsersPageDialogs;
