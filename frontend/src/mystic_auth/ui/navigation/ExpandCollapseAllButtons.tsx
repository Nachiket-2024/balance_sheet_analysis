import React from "react";
import { useTranslation } from "react-i18next";
import { Button } from "../buttons/Button";

interface ExpandCollapseAllButtonsProps {
    onExpandAll: () => void;
    onCollapseAll: () => void;
    expandDisabled?: boolean;
    collapseDisabled?: boolean;
    className?: string;
}

/**
 * Shared "Expand all" / "Collapse all" button pair, used wherever a page
 * groups content into collapsible cards (PermissionsPage, PoliciesPage).
 */
const ExpandCollapseAllButtons: React.FC<ExpandCollapseAllButtonsProps> = ({
    onExpandAll,
    onCollapseAll,
    expandDisabled,
    collapseDisabled,
    className,
}) => {
    const { t } = useTranslation("ui_text");

    return (
        <div className={className ?? "flex items-center justify-end gap-2"}>
            <Button size="sm" onClick={onExpandAll} disabled={expandDisabled} variant="secondary">
                {t("ui_text:expandCollapseAll.expandAll")}
            </Button>
            <Button size="sm" onClick={onCollapseAll} disabled={collapseDisabled} variant="secondary">
                {t("ui_text:expandCollapseAll.collapseAll")}
            </Button>
        </div>
    );
};

export default ExpandCollapseAllButtons;
