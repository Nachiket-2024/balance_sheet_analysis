import React, { useLayoutEffect, useRef } from "react";
import { FileText, Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";

interface PolicyDialogTabsProps {
    activeTab: "details" | "edit";
    showEdit: boolean;
    editDisabled?: boolean;
    editDisabledLabel?: string;
    onDetails: () => void;
    onEdit: () => void;
}

/** The top-level Details/Edit navigation shared by the policy dialogs. */
const PolicyDialogTabs: React.FC<PolicyDialogTabsProps> = ({ activeTab, showEdit, editDisabled = false, editDisabledLabel, onDetails, onEdit }) => {
    const { t } = useTranslation("policies");
    const tabs: Array<"details" | "edit"> = showEdit ? ["details", "edit"] : ["details"];
    const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
    const activeTabIndex = activeTab === "edit" && showEdit && !editDisabled ? 1 : 0;

    // Match UserAccessDialog: the selected tab receives focus when the
    // dialog opens (including when an Edit card action opens directly on the
    // Edit tab), so Arrow/Home/End work immediately without an extra Tab.
    useLayoutEffect(() => {
        tabRefs.current[activeTabIndex]?.focus();
    }, [activeTabIndex]);

    const activate = (tab: "details" | "edit") => {
        if (tab === "details") onDetails();
        else if (!editDisabled) onEdit();
        requestAnimationFrame(() => tabRefs.current[tabs.indexOf(tab)]?.focus());
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, current: "details" | "edit") => {
        const index = tabs.indexOf(current);
        const nextIndex =
            event.key === "ArrowRight" || event.key === "ArrowDown" ? (index + 1) % tabs.length :
                event.key === "ArrowLeft" || event.key === "ArrowUp" ? (index + tabs.length - 1) % tabs.length :
                    event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : index;
        if (nextIndex !== index) {
            event.preventDefault();
            activate(tabs[nextIndex]);
        }
    };

    return (
        <div className="pointer-events-none sticky top-0 z-10 flex items-center gap-2 bg-bg-canvas px-5 pt-4 pb-2 pe-14 sm:px-6 sm:pe-16">
            <div role="tablist" aria-label={t("detailsDialog.topTabsAriaLabel")} className="pointer-events-auto flex min-w-0 flex-1 items-center gap-0 overflow-hidden rounded-lg border border-border-strong bg-bg-surface">
                <button
                    ref={(element) => { tabRefs.current[0] = element; }}
                    id="policy-dialog-tab-details"
                    type="button"
                    role="tab"
                    aria-selected={activeTab === "details"}
                    aria-controls="policy-dialog-panel-details"
                    tabIndex={activeTab === "details" ? 0 : -1}
                    onClick={() => activate("details")}
                    onKeyDown={(event) => handleKeyDown(event, "details")}
                    className="inline-flex h-9 min-w-0 flex-1 cursor-pointer items-center justify-center gap-2 px-3 text-sm font-semibold text-fg-muted transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] hover:bg-brand-subtle hover:text-brand-fg focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-[-2px]"
                    style={activeTab === "details" ? { backgroundColor: "var(--brand-tile-subtle)", color: "var(--brand-fg)", boxShadow: "inset 0 0 0 2px var(--brand-solid)" } : undefined}
                >
                    <FileText size={16} aria-hidden="true" />
                    {t("detailsDialog.tabDetails")}
                </button>
                {showEdit && (
                    <button
                        ref={(element) => { tabRefs.current[1] = element; }}
                        id="policy-dialog-tab-edit"
                        type="button"
                        role="tab"
                    aria-selected={activeTab === "edit"}
                    aria-controls="policy-dialog-panel-edit"
                    tabIndex={activeTab === "edit" && !editDisabled ? 0 : -1}
                    aria-disabled={editDisabled || undefined}
                    disabled={editDisabled}
                    title={editDisabled ? editDisabledLabel : undefined}
                    onClick={() => activate("edit")}
                        onKeyDown={(event) => handleKeyDown(event, "edit")}
                        className="inline-flex h-9 min-w-0 flex-1 cursor-pointer items-center justify-center gap-2 border-l border-border-strong px-3 text-sm font-semibold text-fg-muted transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] hover:bg-brand-subtle hover:text-brand-fg focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-[-2px]"
                    style={activeTab === "edit" && !editDisabled ? { backgroundColor: "var(--brand-tile-subtle)", color: "var(--brand-fg)", boxShadow: "inset 0 0 0 2px var(--brand-solid)" } : undefined}
                    >
                        <Pencil size={16} aria-hidden="true" />
                        {t("detailsDialog.tabEdit")}
                    </button>
                )}
            </div>
        </div>
    );
};

export default PolicyDialogTabs;
