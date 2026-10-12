import React from "react";
import { MousePointerClick, ShieldCheck, Key, UserCog, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { IfCan } from "../../authorization/IfCan";
import { PERMISSIONS } from "../../authorization/permissions";
import AppTooltip from "../../ui/feedback/AppTooltip";
import { Button, type ButtonProps } from "../../ui/buttons/Button";

interface BulkActionToolbarProps {
    /** Number of users a bulk action would apply to: just the current
     * page's checked rows normally, or every row matching the active
     * filters once `selectAllMatching` is on. */
    selectedCount: number;
    onBulkAssignPolicy: () => void;
    onBulkGrantPermission: () => void;
    onBulkSetRole: () => void;
    onClearSelection: () => void;
    /** Whether clicking anywhere in a row toggles selection. Off by default
     * because always-on would fight double-click/drag-select of cell text.
     * See DataTable's `rowClickSelects` doc. */
    rowClickSelects: boolean;
    onToggleRowClickSelects: () => void;
    /** Rows checked on the current page - used only to decide whether the
     * "select all N matching filters" prompt applies (every loaded row is
     * already checked, and there's more to select beyond this page). */
    pageSelectedCount: number;
    pageRowCount: number;
    /** Total rows matching the active filters, across every page. */
    totalMatching: number;
    selectAllMatching: boolean;
    onSelectAllMatching: () => void;
    isSelectingAllMatching: boolean;
}

/** Renders above the users table. Buttons stay visible but disabled while
 * nothing is selected, so bulk actions are discoverable up front. Each
 * button opens the matching Bulk*Dialog, applying one chosen
 * policy/permission/role to every selected user. */
const BulkActionToolbar: React.FC<BulkActionToolbarProps> = ({
    selectedCount, onBulkAssignPolicy, onBulkGrantPermission, onBulkSetRole, onClearSelection,
    rowClickSelects, onToggleRowClickSelects,
    pageSelectedCount, pageRowCount, totalMatching, selectAllMatching, onSelectAllMatching, isSelectingAllMatching,
}) => {
    const { t } = useTranslation(["users", "ui_text"]);
    const noSelection = selectedCount === 0;
    // A plain opacity dip on a disabled button reads as barely different
    // from enabled at this solid-brand saturation, so these three
    // consequential actions switch to outline while there's nothing to act
    // on and only fill solid once a selection makes them actionable -
    // a clearer "not ready yet" signal than opacity alone.
    const privilegedActionProps: Pick<ButtonProps, "variant"> = noSelection
        ? { variant: "brand-tinted-outline" }
        : { variant: "brand" };
    // Only offer "select all matching" once every row loaded on this page
    // is already checked and there's more beyond it - otherwise the prompt
    // would be offering to expand a selection that isn't even "all of this
    // page" yet.
    const canOfferSelectAllMatching =
        !selectAllMatching && pageRowCount > 0 && pageSelectedCount === pageRowCount && totalMatching > pageRowCount;

    return (
        <div className="flex flex-col gap-2 mb-3 rounded-xl border border-border-card bg-bg-surface/70 p-2.5 shadow-card sm:p-3">
            {canOfferSelectAllMatching && (
                <div className="flex items-center gap-2 text-sm text-fg-muted">
                    <p>{t("users:bulkActions.pageSelected", { count: pageRowCount })}</p>
                    <Button size="xs" variant="ghost" onClick={onSelectAllMatching} loading={isSelectingAllMatching}>
                        {t("users:bulkActions.selectAllMatching", { count: totalMatching })}
                    </Button>
                </div>
            )}
            {selectAllMatching && (
                <p className="text-sm text-brand-fg">
                    {t("users:bulkActions.allMatchingSelected", { count: totalMatching })}
                </p>
            )}
            <div className="flex items-center justify-between gap-2 flex-wrap">
            <p className="text-base text-fg-muted">
                {t("ui_text:selectedCount", { count: selectedCount })}
            </p>
            <div className="flex items-center gap-2 flex-wrap">
                <AppTooltip content={t("users:bulkActions.rowClickSelectTitle")}>
                    {/* Same solid brand fill as ChangePasswordCard's submit
                        button once active; off state matches
                        DashboardIdentityCard's "Change Password" quick-link
                        button (variant="outline", border-strong at rest,
                        brand tint on hover). */}
                    <Button
                        size="sm"
                        variant={rowClickSelects ? "brand" : "outline"}
                        className={
                            rowClickSelects
                                ? undefined
                                : "border-border-strong bg-bg-surface text-fg-muted hover:bg-brand-subtle hover:border-brand-solid hover:text-brand-fg"
                        }
                        onClick={onToggleRowClickSelects}
                        aria-pressed={rowClickSelects}
                    >
                        <MousePointerClick size={14} aria-hidden="true" />
                        {t("users:bulkActions.rowClickSelect")}
                    </Button>
                </AppTooltip>
                <IfCan action={PERMISSIONS.POLICIES_ASSIGN}>
                    <Button size="sm" onClick={onBulkAssignPolicy} disabled={noSelection} {...privilegedActionProps}>
                        <ShieldCheck size={14} aria-hidden="true" />
                        {t("users:bulkActions.assignPolicy")}
                    </Button>
                </IfCan>
                <IfCan action={PERMISSIONS.PERMISSIONS_GRANT}>
                    <Button size="sm" onClick={onBulkGrantPermission} disabled={noSelection} {...privilegedActionProps}>
                        <Key size={14} aria-hidden="true" />
                        {t("users:bulkActions.grantPermission")}
                    </Button>
                </IfCan>
                <IfCan action={PERMISSIONS.USERS_ASSIGN_ROLE}>
                    <Button size="sm" onClick={onBulkSetRole} disabled={noSelection} {...privilegedActionProps}>
                        <UserCog size={14} aria-hidden="true" />
                        {t("users:bulkActions.setRole")}
                    </Button>
                </IfCan>
                <Button size="sm" variant="secondary" onClick={onClearSelection} disabled={noSelection}>
                    <X size={14} aria-hidden="true" />
                    {t("ui_text:clearSelection")}
                </Button>
            </div>
            </div>
        </div>
    );
};

export default BulkActionToolbar;
