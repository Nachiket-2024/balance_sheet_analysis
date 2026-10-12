import { Ban, Eye, KeyRound, MoreHorizontal, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import type { TFunction } from "i18next";

import Badge from "../ui/badges/Badge";
import type { DataTableColumn } from "../ui/DataTable/DataTable";
import TableActionIconButton from "../ui/table_actions/TableActionIconButton";
import { Button } from "../ui/buttons/Button";
import StyledSelect from "../ui/filters/StyledSelect";
import AppTooltip from "../ui/feedback/AppTooltip";
import { Avatar, AvatarFallback } from "../ui/shadcn/avatar";
import { cn } from "../ui/styles/classNames";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "../ui/shadcn/dropdown-menu";
import { formatDateTime, formatRelativeTime } from "../ui/dates/dateFormatters";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import type { ManagedUserRead } from "../api/users_api";
import type { SupportedLanguage } from "../translations/translations";

export const ROLE_OPTIONS = ["user", "admin", "system"] as const;

export function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

/** First letter of up to two words of a name, e.g. "Amara Chen" -> "AC" -
 * mirrors design/users.html's row avatar so the table reads the same as the
 * mockup instead of a bare initial or a generic person icon. */
function initialsFor(name: string): string {
    return name
        .split(" ")
        .filter(Boolean)
        .map((part) => part[0])
        .slice(0, 2)
        .join("")
        .toUpperCase();
}

interface BuildUsersColumnsParams {
    t: TFunction<["users", "ui_text"]>;
    language: SupportedLanguage;
    currentUserEmail: string | null | undefined;
    onRoleChangeRequest: (user: ManagedUserRead, role: string) => void;
    /** Opens the unified UserAccessDialog straight to one of its tabs - each
     * row icon (View/Policies/Permissions) still jumps to its own tab, they
     * just share one dialog now instead of three. */
    onOpenAccess: (user: ManagedUserRead, tab: "details" | "policies" | "permissions") => void;
    onReactivate: (email: string) => void;
    reactivatingEmail: string | undefined;
    onPurgeRequest: (user: ManagedUserRead) => void;
    onDeleteRequest: (user: ManagedUserRead) => void;
}

/** UsersPage's DataTable column definitions, built from a params object
 * (not a plain array) since they need page state/handlers to render
 * per-row actions. */
export function buildUsersColumns({
    t,
    language,
    currentUserEmail,
    onRoleChangeRequest,
    onOpenAccess,
    onReactivate,
    reactivatingEmail,
    onPurgeRequest,
    onDeleteRequest,
}: BuildUsersColumnsParams): DataTableColumn<ManagedUserRead>[] {
    return [
        {
            key: "name",
            header: `${t("users:columns.name")} / ${t("users:columns.email")}`,
            sortable: true,
            // Wider than the old separate Name/Email columns combined -
            // this is now the table's one flexible identity column
            // (design/users.html), holding an avatar plus stacked name/email.
            width: "20rem",
            render: (u) => (
                <div className="flex min-w-0 items-center gap-2.5">
                    <Avatar>
                        <AvatarFallback className="border border-border bg-muted font-semibold text-fg-default">
                            {initialsFor(u.name)}
                        </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                        <p className="flex min-w-0 items-center gap-1.5 font-medium">
                            <AppTooltip content={u.name}>
                                <span className="truncate">{u.name}</span>
                            </AppTooltip>
                            {u.email === currentUserEmail && (
                                <Badge className="shrink-0" colorPalette="brand" variant="subtle" size="sm">
                                    {t("users:columns.you")}
                                </Badge>
                            )}
                        </p>
                        <AppTooltip content={u.email}>
                            <p className="truncate text-[13px] leading-tight text-fg-muted">{u.email}</p>
                        </AppTooltip>
                    </div>
                </div>
            ),
        },
        {
            key: "role",
            header: t("users:columns.role"),
            sortable: true,
            width: "9.375rem",
            render: (u) => (
                <IfCan
                    action={PERMISSIONS.USERS_ASSIGN_ROLE}
                    fallback={
                        <p className={cn("capitalize", !u.role && "text-fg-muted")}>
                            {u.role ?? t("users:columns.noRoleAssigned")}
                        </p>
                    }
                >
                    <StyledSelect
                        className="w-32"
                        value={u.role ?? ""}
                        onChange={(value) => onRoleChangeRequest(u, value)}
                        ariaLabel={t("users:columns.changeRoleAriaLabel", { email: u.email })}
                        textTransform="capitalize"
                        options={ROLE_OPTIONS.map((role) => ({ value: role, label: capitalize(role) }))}
                        disabled={u.email === currentUserEmail || u.role === "system"}
                        title={
                            u.email === currentUserEmail
                                ? t("users:columns.cannotChangeOwnRole")
                                : u.role === "system"
                                  ? t("users:columns.cannotModifySystemUser")
                                  : undefined
                        }
                    />
                </IfCan>
            ),
        },
        {
            key: "status",
            header: t("users:columns.status"),
            width: "10.625rem",
            // Deactivated wins outright rather than stacking alongside
            // verified/unverified: a deactivated account can't sign in
            // either way, so whether it was ever verified isn't the thing
            // a permission holder scanning this column needs to see first. One pill,
            // not two, since there's no longer a second line to align
            // against.
            render: (u) =>
                !u.is_active ? (
                    <Badge colorPalette="red" variant="outline" size="md">
                        {t("users:columns.deactivated")}
                    </Badge>
                ) : u.is_verified ? (
                    // Same box model as Badge (padding/border/radius), just
                    // transparent, so "Verified" starts at the same
                    // x-position a pill like "Unverified" would.
                                <span className="inline-flex items-center whitespace-nowrap rounded-md border border-transparent px-2.5 py-1 text-sm font-semibold text-fg-muted">
                                    {t("users:columns.verified")}
                                </span>
                ) : (
                    <Badge colorPalette="yellow" variant="outline" size="md">
                        {t("users:columns.unverified")}
                    </Badge>
                ),
        },
        {
            key: "last_login_at",
            header: t("users:columns.lastLogin"),
            sortable: true,
            width: "9.75rem",
            render: (u) =>
                u.last_login_at ? (
                    <div>
                        <p className="text-sm font-medium">{formatRelativeTime(u.last_login_at, language)}</p>
                        <p className="text-[13px] leading-tight text-fg-subtle">{formatDateTime(u.last_login_at, language)}</p>
                    </div>
                ) : (
                    <span className="text-sm text-fg-subtle" title={t("users:columns.neverSignedIn")}>
                        {t("users:columns.neverSignedInShort")}
                    </span>
                ),
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            // Icon-only buttons, not text pills: some translated labels run
            // 4-5x wider than English, and icons keep every row's actions
            // on one line regardless of locale.
            width: "14rem",
            render: (u) => (
                <div className="flex items-center justify-end gap-1.5 flex-nowrap">
                    <TableActionIconButton colorPalette="neutral" label={t("users:columns.view")} onClick={() => onOpenAccess(u, "details")}>
                        <Eye size={18} aria-hidden="true" />
                    </TableActionIconButton>
                    <IfCan action={PERMISSIONS.POLICIES_READ}>
                        <TableActionIconButton
                            colorPalette="neutral"
                            label={t("users:columns.policies")}
                            onClick={() => onOpenAccess(u, "policies")}
                        >
                            <ShieldCheck size={18} aria-hidden="true" />
                        </TableActionIconButton>
                    </IfCan>
                    <IfCan action={PERMISSIONS.PERMISSIONS_READ}>
                        <TableActionIconButton
                            colorPalette="neutral"
                            label={t("users:columns.permissions")}
                            onClick={() => onOpenAccess(u, "permissions")}
                        >
                            <KeyRound size={18} aria-hidden="true" />
                        </TableActionIconButton>
                    </IfCan>
                    {/* The reserved system account cannot be deactivated or
                        deleted by the API. Do not expose a More menu whose
                        only destructive actions can never succeed - unlike
                        the self-account case below, there's no explanation
                        worth surfacing since a system row is never the
                        caller's own account. */}
                    {u.role !== "system" ? (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    aria-label={t("users:columns.moreActions", { defaultValue: "More actions" })}
                                    className="text-fg-muted hover:bg-brand-tile-subtle hover:text-brand-fg"
                                >
                                    <MoreHorizontal size={18} aria-hidden="true" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {u.deleted_at ? (
                                    <IfCan action={PERMISSIONS.USERS_REACTIVATE}>
                                        <DropdownMenuItem onSelect={() => onReactivate(u.email)} disabled={reactivatingEmail === u.email}>
                                            <RotateCcw size={16} aria-hidden="true" />
                                            {t("users:columns.reactivate")}
                                        </DropdownMenuItem>
                                    </IfCan>
                                ) : (
                                    <IfCan action={PERMISSIONS.USERS_DEACTIVATE_ANY}>
                                        {/* Own row: shown, not hidden, but disabled with an
                                            explanation on hover/focus (AppTooltip), same
                                            "explain a disabled action" contract
                                            TableActionIconButton's disabledLabel gives the
                                            row's other icon buttons - a caller who opens this
                                            menu on their own row should learn why Deactivate
                                            doesn't work, not just find it missing. */}
                                        <AppTooltip
                                            content={
                                                u.email === currentUserEmail
                                                    ? t("users:columns.cannotDeactivateOwnAccount")
                                                    : undefined
                                            }
                                        >
                                            <DropdownMenuItem
                                                onSelect={() => onDeleteRequest(u)}
                                                disabled={u.email === currentUserEmail}
                                            >
                                                <Ban size={16} aria-hidden="true" />
                                                {t("users:columns.deactivate")}
                                            </DropdownMenuItem>
                                        </AppTooltip>
                                    </IfCan>
                                )}
                                {u.deleted_at && <DropdownMenuSeparator />}
                                {u.deleted_at && (
                                    <IfCan action={PERMISSIONS.USERS_DELETE_ANY}>
                                        <AppTooltip
                                            content={
                                                u.email === currentUserEmail
                                                    ? t("users:columns.cannotDeleteOwnAccount")
                                                    : undefined
                                            }
                                        >
                                            <DropdownMenuItem
                                                variant="destructive"
                                                onSelect={() => onPurgeRequest(u)}
                                                disabled={u.email === currentUserEmail}
                                            >
                                                <Trash2 size={16} aria-hidden="true" />
                                                {t("ui_text:delete")}
                                            </DropdownMenuItem>
                                        </AppTooltip>
                                    </IfCan>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    ) : (
                        <span className="size-8 shrink-0" aria-hidden="true" />
                    )}
                </div>
            ),
        },
    ];
}
