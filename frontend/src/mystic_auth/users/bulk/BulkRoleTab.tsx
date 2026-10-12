import React from "react";
import { useTranslation } from "react-i18next";

import { Button } from "../../ui/buttons/Button";
import { Switch } from "../../ui/shadcn/switch";
import { useAuthorization } from "../../authorization/useAuthorization";
import { PERMISSIONS } from "../../authorization/permissions";
import { ROLE_OPTIONS, capitalize } from "../usersColumns";

interface BulkRoleTabProps { role: string; isPending: boolean; onRoleChange: (role: string) => void; onRun: () => void; }

const BulkRoleTab: React.FC<BulkRoleTabProps> = ({ role, isPending, onRoleChange, onRun }) => {
    const { t } = useTranslation("users");
    const { can } = useAuthorization();
    const canAssignSystemRole = can(PERMISSIONS.USERS_ASSIGN_SYSTEM_ROLE);
    // "system" is a reserved, protected role: a caller without users:assign_system_role
    // never sees it as an option at all, rather than seeing it disabled with an
    // explanatory tooltip. Hiding what a caller cannot use is preferred here to
    // showing-then-blocking it, consistent with every other permission-gated
    // control in this app (policy edit tabs, permission grant/revoke buttons, etc).
    const visibleOptions = ROLE_OPTIONS.filter((option) => option !== "system" || canAssignSystemRole);
    return <div className="space-y-3"><div className="grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label={t("bulkActions.selectRoleAriaLabel")}>{visibleOptions.map((option) => <label key={option} className="flex items-center justify-between rounded-lg border border-border-default bg-bg-surface px-3 py-2.5 cursor-pointer hover:bg-row-hover"><span className="text-sm font-medium">{capitalize(option)}</span><Switch checked={role === option} onCheckedChange={(checked) => onRoleChange(checked ? option : "")} aria-label={capitalize(option)} /></label>)}</div><Button size="sm" variant="brand" onClick={onRun} disabled={!role} loading={isPending}>{t("bulkActions.setRoleForSelected")}</Button></div>;
};

export default BulkRoleTab;
