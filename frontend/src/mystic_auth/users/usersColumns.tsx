import { Badge, HStack, Text } from "@chakra-ui/react";
import type { TFunction } from "i18next";

import type { DataTableColumn } from "../ui/DataTable";
import TableActionButton from "../ui/TableActionButton";
import StyledSelect from "../ui/StyledSelect";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import type { ManagedUserRead } from "../api/users_api";

export const ROLE_OPTIONS = ["user", "admin", "system"] as const;

export function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

interface BuildUsersColumnsParams {
    t: TFunction<["users", "ui_text"]>;
    currentUserEmail: string | null | undefined;
    onRoleChangeRequest: (user: ManagedUserRead, role: string) => void;
    onView: (user: ManagedUserRead) => void;
    onPolicies: (email: string) => void;
    onReactivate: (email: string) => void;
    reactivatingEmail: string | undefined;
    onPurgeRequest: (user: ManagedUserRead) => void;
    onDeleteRequest: (user: ManagedUserRead) => void;
}

/** UsersPage's DataTable column definitions, extracted since they need the
 * page's own state/handlers (current user, pending dialogs, in-flight
 * mutations) to render per-row actions - unlike the audit_log/ tables'
 * columns.tsx files, which are pure display with no row-level interaction,
 * these are built from a params object rather than exported as a plain
 * array. */
export function buildUsersColumns({
    t,
    currentUserEmail,
    onRoleChangeRequest,
    onView,
    onPolicies,
    onReactivate,
    reactivatingEmail,
    onPurgeRequest,
    onDeleteRequest,
}: BuildUsersColumnsParams): DataTableColumn<ManagedUserRead>[] {
    return [
        {
            key: "name",
            header: t("users:columns.name"),
            sortable: true,
            width: "22%",
            truncate: true,
            render: (u) => (
                <Text fontWeight="medium">
                    {u.name}
                    {u.email === currentUserEmail && (
                        <Badge ml={2} colorPalette="brand" variant="subtle" size="md">
                            {t("users:columns.you")}
                        </Badge>
                    )}
                </Text>
            ),
        },
        { key: "email", header: t("users:columns.email"), sortable: true, width: "26%", truncate: true, render: (u) => u.email },
        {
            key: "role",
            header: t("users:columns.role"),
            sortable: true,
            width: "150px",
            render: (u) => (
                <IfCan
                    action={PERMISSIONS.USERS_ASSIGN_ROLE}
                    fallback={
                        <Text textTransform="capitalize" color={u.role ? undefined : "fg.muted"}>
                            {u.role ?? t("users:columns.noRoleAssigned")}
                        </Text>
                    }
                >
                    <StyledSelect
                        w="130px"
                        value={u.role ?? ""}
                        onChange={(value) => onRoleChangeRequest(u, value)}
                        ariaLabel={t("users:columns.changeRoleAriaLabel", { email: u.email })}
                        textTransform="capitalize"
                        options={ROLE_OPTIONS.map((role) => ({ value: role, label: capitalize(role) }))}
                        disabled={u.email === currentUserEmail}
                        title={u.email === currentUserEmail ? t("users:columns.cannotChangeOwnRole") : undefined}
                    />
                </IfCan>
            ),
        },
        {
            key: "status",
            header: t("users:columns.status"),
            width: "170px",
            render: (u) => (
                <HStack gap={1}>
                    <Badge colorPalette={u.is_verified ? "green" : "yellow"} size="md">
                        {u.is_verified ? t("users:columns.verified") : t("users:columns.unverified")}
                    </Badge>
                    {u.deleted_at ? (
                        <Badge colorPalette="red" size="md">{t("users:columns.deleted")}</Badge>
                    ) : (
                        !u.is_active && <Badge colorPalette="red" size="md">{t("ui_text:inactive")}</Badge>
                    )}
                </HStack>
            ),
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            // A deleted row shows up to 4 buttons at once (View + Policies +
            // Reactivate + Purge); 230px was only wide enough for ~2,
            // wrapping onto a second line. Wide enough for all four on one
            // line, on every row shape (1/2/3/4 buttons) this column ever
            // renders.
            width: "400px",
            render: (u) => (
                <HStack justify="flex-end" gap={2} wrap="wrap">
                    <TableActionButton colorPalette="blue" onClick={() => onView(u)}>
                        {t("users:columns.view")}
                    </TableActionButton>
                    <IfCan action={PERMISSIONS.POLICIES_READ}>
                        <TableActionButton colorPalette="purple" onClick={() => onPolicies(u.email)}>
                            {t("users:columns.policies")}
                        </TableActionButton>
                    </IfCan>
                    {u.deleted_at ? (
                        <>
                            <IfCan action={PERMISSIONS.USERS_REACTIVATE}>
                                <TableActionButton
                                    colorPalette="green"
                                    onClick={() => onReactivate(u.email)}
                                    loading={reactivatingEmail === u.email}
                                >
                                    {t("users:columns.reactivate")}
                                </TableActionButton>
                            </IfCan>
                            <IfCan action={PERMISSIONS.USERS_PURGE}>
                                <TableActionButton
                                    colorPalette="red"
                                    onClick={() => onPurgeRequest(u)}
                                    disabled={u.email === currentUserEmail}
                                >
                                    {t("users:columns.purge")}
                                </TableActionButton>
                            </IfCan>
                        </>
                    ) : (
                        <IfCan action={PERMISSIONS.USERS_DELETE_ANY}>
                            <TableActionButton
                                colorPalette="red"
                                onClick={() => onDeleteRequest(u)}
                                disabled={u.email === currentUserEmail}
                            >
                                {t("ui_text:delete")}
                            </TableActionButton>
                        </IfCan>
                    )}
                </HStack>
            ),
        },
    ];
}
