import React, { useState } from "react";
import { CalendarDays, History, ListChecks, Lock, Settings2, ShieldCheck, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import Badge from "../../ui/badges/Badge";
import { Button } from "../../ui/buttons/Button";
import FormAlert from "../../ui/feedback/FormAlert";
import { IfCan } from "../../authorization/IfCan";
import { PERMISSIONS } from "../../authorization/permissions";
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "../../ui/shadcn/dialog";
import { formatDateTime } from "../../ui/dates/dateFormatters";
import { useLanguageStore } from "../../store/languageStore";
import PolicyActionGroups from "../PolicyActionGroups";
import { displayAuthorizationDescription, formatResourceTypeLabel, PROTECTED_POLICY_NAMES, RESOURCE_TYPE_ICONS } from "../policyCardHelpers";
import { cn } from "../../ui/styles/classNames";
import PolicyDialogTabs from "./PolicyDialogTabs";
import PolicyHistorySection from "./PolicyHistorySection";
import { useCan } from "../../authorization/useCan";
import {
    DIALOG_BODY_CLASSNAME,
    DIALOG_DETAIL_LABEL_CLASSNAME,
    DIALOG_DETAIL_VALUE_CLASSNAME,
    DIALOG_FOOTER_CLASSNAME,
    DIALOG_HEADER_CLASSNAME,
    DIALOG_PANEL_CLASSNAME,
    DIALOG_SECTION_CLASSNAME,
} from "../../ui/styles/dialogStyles";
import type { PolicyRead } from "../../api/policies_api";
import type { PolicyFormValues } from "./PolicyFormDialog";
import PolicyFormDialog from "./PolicyFormDialog";

interface PolicyDetailsDialogProps {
    isOpen: boolean;
    policy: PolicyRead | null;
    onClose: () => void;
    /** Opens PolicyFormDialog pre-filled for this policy - omitted by
     * callers (e.g. UserPoliciesDialog's read-only preview) that have no
     * edit flow to hand off to. */
    onEdit?: (policy: PolicyRead) => void;
    isSaving?: boolean;
    errorMessage?: string | null;
    onSubmit?: (values: PolicyFormValues) => void;
    onActionsChange?: (actions: string[], rollback: () => void, previousActions: string[], apply: () => void) => void;
    onFormClose?: () => void;
    initialTab?: "details" | "edit";
    triggerElement?: HTMLElement | null;
}

interface DetailRowProps {
    label: string;
    children: React.ReactNode;
}

/** Same label/value layout as UserDetailsDialog's DetailRow. This dialog
 * exists to show what the table's Name/Actions columns truncate, so
 * nothing here should re-truncate. */
const DetailRow: React.FC<DetailRowProps> = ({ label, children }) => (
    <div className="flex flex-col gap-0.5">
        <p className={DIALOG_DETAIL_LABEL_CLASSNAME}>
            {label}
        </p>
        <div className={DIALOG_DETAIL_VALUE_CLASSNAME}>
            {children}
        </div>
    </div>
);

/**
 * PolicyDetailsDialog
 * ----------------------------
 * Read-only "View" panel for one policy's full name/description/actions/
 * conditions, everything PoliciesPage's table truncates or hides entirely
 * (conditions isn't a column at all). Takes the already-fetched row object
 * directly, no separate query, same as UserDetailsDialog.
 */

const DetailSectionHeading: React.FC<{ icon: React.ReactNode; children: React.ReactNode }> = ({ icon, children }) => (
    <div className="mb-3 flex items-center gap-3">
        <span className="grid size-9 shrink-0 place-items-center text-fg-muted">
            {icon}
        </span>
        <span className="text-xs font-semibold uppercase tracking-wide text-fg-muted">{children}</span>
    </div>
);

function humanizeConditionKey(key: string): string {
    const label = key.replace(/[_-]+/g, " ").trim();
    return label ? label.charAt(0).toUpperCase() + label.slice(1) : key;
}

function readableConditionValue(value: unknown): string {
    if (value === null || value === undefined) return "-";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) return value.length ? value.map(readableConditionValue).join(", ") : "-";
    if (typeof value === "object") {
        return Object.entries(value as Record<string, unknown>)
            .map(([key, nestedValue]) => `${humanizeConditionKey(key)}: ${readableConditionValue(nestedValue)}`)
            .join("\n");
    }
    return String(value);
}

const PolicyDetailsDialog: React.FC<PolicyDetailsDialogProps> = ({ isOpen, policy, onClose, onEdit, isSaving = false, errorMessage = null, onSubmit, onActionsChange, onFormClose, initialTab = "details", triggerElement }) => {
    const { t } = useTranslation(["policies", "ui_text"]);
    const navigate = useNavigate();
    const language = useLanguageStore((s) => s.chromeLanguage);
    const canEdit = useCan(PERMISSIONS.POLICIES_UPDATE);
    const isProtected = PROTECTED_POLICY_NAMES.has(policy?.name ?? "");
    const [activeTab, setActiveTab] = useState<"details" | "edit">("details");
    // Reset the shared dialog to its requested entry tab when a different
    // policy or entry point opens it, without an effect-driven extra render.
    const resetKey = `${isOpen}:${policy?.name ?? ""}:${initialTab}`;
    const [previousResetKey, setPreviousResetKey] = useState("");
    if (resetKey !== previousResetKey) {
        setPreviousResetKey(resetKey);
        setActiveTab(initialTab);
    }

    if (!policy) return null;
    const ResourceIcon = RESOURCE_TYPE_ICONS[policy.resource_type] ?? ShieldCheck;
    const effectiveTab = activeTab === "edit" && canEdit && !isProtected ? "edit" : "details";

    // Keep one stable modal root for both Details and Edit. Changing Radix's
    // modal mode while this root is open can leave a stale blurred overlay;
    // the toast layer is above the overlay independently for Undo actions.
    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent
                overlayClassName="backdrop-blur-[2px]"
                closeLabel={t("ui_text:closeDialog")}
                returnFocusElement={triggerElement}
                returnFocusFallback={() => Array.from(document.querySelectorAll<HTMLElement>('button[aria-label="View"][data-policy-name]'))
                    .find((element) => element.dataset.policyName === policy.name) ?? null}
                className={`w-[calc(100vw-1.5rem)] sm:max-w-3xl lg:max-w-[55rem] h-[min(44rem,calc(100svh-1.5rem))] flex flex-col overflow-hidden ${DIALOG_PANEL_CLASSNAME}`}
                // Let the shared primitive complete its normal focus cycle.
                // It captures the triggering icon before Radix moves focus
                // into the dialog, then restores it on close.
            >
                <PolicyDialogTabs
                    activeTab={effectiveTab}
                    showEdit={!!onEdit && canEdit && !!onSubmit}
                    editDisabled={isProtected}
                    editDisabledLabel={t("policies:columns.cannotEditProtectedPolicy")}
                    onDetails={() => setActiveTab("details")}
                    onEdit={() => setActiveTab("edit")}
                />
                <DialogHeader className={cn(DIALOG_HEADER_CLASSNAME, "sticky top-11 z-20 -mx-5 mt-1 bg-bg-canvas px-5 sm:-mx-6 sm:px-6")}>
                    <div className="flex min-w-0 items-center gap-3">
                        <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-brand-solid text-brand-contrast shadow-card">
                            <ResourceIcon size={26} aria-hidden="true" />
                        </div>
                        <div className="min-w-0">
                            <DialogTitle className="break-words text-xl tracking-[-0.02em]">{policy.name}</DialogTitle>
                            <div className="mt-1.5 flex flex-wrap items-center gap-2">
                                <Badge colorPalette="gray" variant="outline" size="sm">
                                    <Settings2 size={12} aria-hidden="true" />
                                    {formatResourceTypeLabel(policy.resource_type)}
                                </Badge>
                                <Badge colorPalette={policy.is_active ? "green" : "gray"} variant="subtle" size="sm">
                                    {policy.is_active ? t("policies:detailsDialog.active") : t("ui_text:inactive")}
                                </Badge>
                                {isProtected && (
                                    <Badge colorPalette="gray" variant="subtle" size="sm">
                                        <Lock size={12} aria-hidden="true" />
                                        {t("policies:columns.protected")}
                                    </Badge>
                                )}
                            </div>
                            <p className="mt-2 max-w-2xl break-words text-sm text-fg-muted">
                                {displayAuthorizationDescription(policy.description, t("policies:detailsDialog.noDescription"))}
                            </p>
                        </div>
                    </div>
                </DialogHeader>
                {effectiveTab === "edit" && onSubmit && onFormClose ? (
                    <PolicyFormDialog
                        isOpen={isOpen}
                        policy={policy}
                        isSaving={isSaving}
                        errorMessage={errorMessage}
                        onSubmit={onSubmit}
                        onActionsChange={onActionsChange}
                        onClose={onFormClose}
                        onDetails={() => setActiveTab("details")}
                        embedded
                    />
                ) : (
                <>
                <div id="policy-dialog-panel-details" role="tabpanel" aria-labelledby="policy-dialog-tab-details" className={DIALOG_BODY_CLASSNAME}>
                    {!canEdit && onSubmit && (
                        <FormAlert status="warning">{t("policies:detailsDialog.authorizationChangedNotice")}</FormAlert>
                    )}
                    <div className="flex flex-col gap-4">
                        {/* Short fields pair up two-per-row instead of each taking a
                            full row, leaving enough headroom for policies with many
                            actions (e.g. system_superuser's 18) to show every badge
                            without the dialog needing its own scroll. */}
                        <section className={DIALOG_SECTION_CLASSNAME}>
                            <DetailSectionHeading icon={<Settings2 size={16} aria-hidden="true" />}>
                                {t("policies:detailsDialog.policyDefinition")}
                            </DetailSectionHeading>
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                    <DetailRow label={t("policies:detailsDialog.name")}>
                                        <span className="break-words font-medium">{policy.name}</span>
                                    </DetailRow>
                                </div>
                                <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                    <DetailRow label={t("policies:detailsDialog.resourceType")}>
                                        <span className="font-medium">{formatResourceTypeLabel(policy.resource_type)}</span>
                                    </DetailRow>
                                </div>
                                <div className="sm:col-span-2">
                                    <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                        <DetailRow label={t("policies:detailsDialog.description")}>
                                            <span className={policy.description ? "break-words" : "text-fg-muted"}>
                                                {displayAuthorizationDescription(policy.description, t("policies:detailsDialog.noDescription"))}
                                            </span>
                                        </DetailRow>
                                    </div>
                                </div>
                            </div>
                        </section>
                        <section className={DIALOG_SECTION_CLASSNAME}>
                            <DetailSectionHeading icon={<ListChecks size={16} aria-hidden="true" />}>
                                {t("policies:detailsDialog.actions")}
                            </DetailSectionHeading>
                            <DetailRow label={t("policies:detailsDialog.actions")}>
                                <PolicyActionGroups actions={policy.actions} />
                            </DetailRow>
                        </section>
                        <section className={DIALOG_SECTION_CLASSNAME}>
                            <DetailSectionHeading icon={<CalendarDays size={16} aria-hidden="true" />}>
                                {t("policies:detailsDialog.lifecycle")}
                            </DetailSectionHeading>
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                    <DetailRow label={t("policies:detailsDialog.status")}>
                                        {policy.is_active ? <Badge colorPalette="green" size="md">{t("policies:detailsDialog.active")}</Badge> : <Badge colorPalette="gray" size="md">{t("ui_text:inactive")}</Badge>}
                                    </DetailRow>
                                </div>
                                <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                    <DetailRow label={t("policies:detailsDialog.created")}><span className="font-medium">{formatDateTime(policy.created_at, language)}</span></DetailRow>
                                </div>
                                <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                    <DetailRow label={t("policies:detailsDialog.lastUpdated")}><span className="font-medium">{formatDateTime(policy.updated_at, language)}</span></DetailRow>
                                </div>
                                {policy.created_by && (
                                    <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                        <DetailRow label={t("policies:detailsDialog.createdBy")}><span className="break-words font-medium">{policy.created_by}</span></DetailRow>
                                    </div>
                                )}
                            </div>
                        </section>
                        <section className={DIALOG_SECTION_CLASSNAME}>
                            <DetailSectionHeading icon={<History size={16} aria-hidden="true" />}>
                                {t("policies:detailsDialog.historyAndConditions")}
                            </DetailSectionHeading>
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                <DetailRow label={t("policies:detailsDialog.conditions")}>
                                    {policy.conditions ? (
                                        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 rounded-md border border-border-card bg-bg-card-head p-3">
                                            {Object.entries(policy.conditions).map(([key, value]) => (
                                                <React.Fragment key={key}>
                                                    <dt className="text-fg-muted">{humanizeConditionKey(key)}</dt>
                                                    <dd className="min-w-0 whitespace-pre-wrap break-words">{readableConditionValue(value)}</dd>
                                                </React.Fragment>
                                            ))}
                                        </dl>
                                    ) : (
                                        <span className="text-fg-muted">{t("policies:detailsDialog.noConditions")}</span>
                                    )}
                                </DetailRow>
                                </div>
                                <div className="rounded-xl border border-border-card bg-bg-surface p-3">
                                <DetailRow label={t("policies:detailsDialog.recentChanges")}>
                                    <PolicyHistorySection
                                        policyName={policy.name}
                                        isOpen={isOpen}
                                        canEdit={canEdit}
                                        isProtected={isProtected}
                                        language={language}
                                        resetKey={resetKey}
                                    />
                                </DetailRow>
                                </div>
                            </div>
                        </section>
                    </div>
                </div>
                <DialogFooter className={DIALOG_FOOTER_CLASSNAME}>
                    <IfCan action={PERMISSIONS.USERS_LIST_ALL}>
                        <Button
                            onClick={() => navigate(`/users?policy=${encodeURIComponent(policy.name)}`)}
                            variant="secondary"
                        >
                            <Users size={16} aria-hidden="true" />
                            {t("policies:detailsDialog.viewPolicyHolders")}
                        </Button>
                    </IfCan>
                    <Button onClick={onClose} variant="secondary">
                        {t("ui_text:close")}
                    </Button>
                </DialogFooter>
                </>
                )}
            </DialogContent>
        </Dialog>
    );
};

export default PolicyDetailsDialog;
