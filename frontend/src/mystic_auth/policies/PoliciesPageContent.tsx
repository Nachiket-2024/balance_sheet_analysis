import React from "react";
import { ShieldCheck, ShieldOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import PageContainer from "../ui/navigation/PageContainer";
import GlossaryHelp from "../ui/display/GlossaryHelp";
import Pagination from "../ui/navigation/Pagination";
import ConfirmDialog from "../ui/feedback/ConfirmDialog";
import FormAlert from "../ui/feedback/FormAlert";
import LoadingState from "../ui/feedback/LoadingState";
import { Button } from "../ui/buttons/Button";
import ExpandCollapseAllButtons from "../ui/navigation/ExpandCollapseAllButtons";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import PolicyFormDialog, { type PolicyFormValues } from "./dialogs/PolicyFormDialog";
import PolicyDetailsDialog from "./dialogs/PolicyDetailsDialog";
import PolicyStatsCard, { type PolicyStatTileKey } from "./PolicyStatsCard";
import PoliciesFilterBar, { ALL_VALUE } from "./PoliciesFilterBar";
import PolicyCard from "./PolicyCard";
import { formatResourceTypeLabel } from "./policyCardHelpers";
import type { PolicyHolderRead, PolicyRead } from "../api/policies_api";

interface PoliciesPageContentProps {
    canReadPolicies: boolean;
    data: { policies: PolicyRead[]; total: number } | undefined;
    allPolicies: PolicyRead[] | undefined;
    isStatsLoading: boolean;
    isFetching: boolean;
    isLoading: boolean;
    isError: boolean;
    refetch: () => void;
    page: number;
    totalPages: number;
    filteredPolicies: PolicyRead[] | undefined;
    groupedByResourceType: [string, PolicyRead[]][];
    search: string;
    resourceType: string;
    status: string;
    containsAction: string;
    destructiveOnly: boolean;
    hasSearchOrFilters: boolean;
    activeTile: PolicyStatTileKey | null;
    openNames: Set<string>;
    togglingName: string | undefined;
    deletingPolicy: PolicyRead | null;
    deletingPolicyHolders: PolicyHolderRead[] | undefined;
    isDeletingPolicyHoldersLoading: boolean;
    isDeletingPolicyHoldersError: boolean;
    refetchDeletingPolicyHolders: () => void;
    editingPolicy: PolicyRead | undefined;
    viewingPolicy: PolicyRead | null;
    viewingPolicyTrigger: HTMLElement | null;
    initialPolicyTab: "details" | "edit";
    formOpen: boolean;
    isSaving: boolean;
    formError: string | null;
    isDeletePending: boolean;
    onPageChange: (page: number) => void;
    onSearchChange: (value: string) => void;
    onResourceTypeChange: (value: string) => void;
    onStatusChange: (value: string) => void;
    onContainsActionChange: (value: string) => void;
    onDestructiveOnlyChange: (value: boolean | ((previous: boolean) => boolean)) => void;
    onClearFilters: () => void;
    onExpandAll: () => void;
    onCollapseAll: () => void;
    allOpen: boolean;
    noneOpen: boolean;
    onCreate: () => void;
    onEdit: (policy: PolicyRead) => void;
    onView: (policy: PolicyRead | null, trigger?: HTMLElement) => void;
    onToggleOpen: (policyName: string) => void;
    onToggleActive: (policy: PolicyRead) => void;
    onDeleteRequest: (policy: PolicyRead | null) => void;
    onSubmit: (values: PolicyFormValues) => void;
    onActionsChange: (actions: string[], rollback: () => void, previousActions: string[], apply: () => void) => void;
    onCloseForm: () => void;
    onConfirmDelete: () => void;
}

const PoliciesPageContent: React.FC<PoliciesPageContentProps> = ({
    canReadPolicies,
    data,
    allPolicies,
    isStatsLoading,
    isFetching,
    isLoading,
    isError,
    refetch,
    page,
    totalPages,
    filteredPolicies,
    groupedByResourceType,
    search,
    resourceType,
    status,
    containsAction,
    destructiveOnly,
    hasSearchOrFilters,
    activeTile,
    openNames,
    togglingName,
    deletingPolicy,
    deletingPolicyHolders,
    isDeletingPolicyHoldersLoading,
    isDeletingPolicyHoldersError,
    refetchDeletingPolicyHolders,
    editingPolicy,
    viewingPolicy,
    viewingPolicyTrigger,
    initialPolicyTab,
    formOpen,
    isSaving,
    formError,
    isDeletePending,
    onPageChange,
    onSearchChange,
    onResourceTypeChange,
    onStatusChange,
    onContainsActionChange,
    onDestructiveOnlyChange,
    onClearFilters,
    onExpandAll,
    onCollapseAll,
    allOpen,
    noneOpen,
    onCreate,
    onEdit,
    onView,
    onToggleOpen,
    onToggleActive,
    onDeleteRequest,
    onSubmit,
    onActionsChange,
    onCloseForm,
    onConfirmDelete,
}) => {
    const { t } = useTranslation(["policies", "ui_text"]);
    const renderCard = (policy: PolicyRead) => (
        <PolicyCard
            key={policy.id}
            policy={policy}
            isOpen={openNames.has(policy.name)}
            onToggleOpen={onToggleOpen}
            onView={onView}
            onEdit={onEdit}
            onToggleActive={onToggleActive}
            isTogglingActive={togglingName === policy.name}
            onDeleteRequest={onDeleteRequest}
        />
    );

    return (
        <PageContainer
            title={t("policies:page.title")}
            icon={ShieldCheck}
            titleExtra={
                <GlossaryHelp
                    ariaLabel={t("policies:page.glossaryAriaLabel")}
                    items={[
                        { term: t("policies:page.glossary.policy.term"), definition: t("policies:page.glossary.policy.definition") },
                        { term: t("policies:page.glossary.resourceType.term"), definition: t("policies:page.glossary.resourceType.definition") },
                        { term: t("policies:page.glossary.destructive.term"), definition: t("policies:page.glossary.destructive.definition") },
                        { term: t("policies:page.glossary.protected.term"), definition: t("policies:page.glossary.protected.definition") },
                    ]}
                />
            }
            description={t("policies:page.description")}
            actions={
                <IfCan action={PERMISSIONS.POLICIES_CREATE}>
                    <Button variant="brand" onClick={onCreate}>{t("policies:page.createPolicy")}</Button>
                </IfCan>
            }
            headerExtra={canReadPolicies ? (
                <div className="flex flex-col gap-4">
                    <PolicyStatsCard
                        policies={allPolicies}
                        isLoading={isStatsLoading}
                        activeTile={activeTile}
                        onFilterTotal={onClearFilters}
                        onFilterActive={() => {
                            onDestructiveOnlyChange(false);
                            onResourceTypeChange(ALL_VALUE);
                            onSearchChange("");
                            onStatusChange("true");
                        }}
                        onFilterInactive={() => {
                            onDestructiveOnlyChange(false);
                            onResourceTypeChange(ALL_VALUE);
                            onSearchChange("");
                            onStatusChange("false");
                        }}
                        onFilterDestructive={() => onDestructiveOnlyChange((value) => !value)}
                    />
                    <PoliciesFilterBar
                        search={search}
                        setSearch={onSearchChange}
                        resourceType={resourceType}
                        setResourceType={onResourceTypeChange}
                        status={status}
                        setStatus={onStatusChange}
                        containsAction={containsAction}
                        setContainsAction={onContainsActionChange}
                        allPolicies={allPolicies}
                        isFetching={isFetching}
                        totalResults={data?.total}
                        destructiveOnly={destructiveOnly}
                        setDestructiveOnly={onDestructiveOnlyChange}
                    />
                </div>
            ) : undefined}
        >
            {!canReadPolicies ? <FormAlert status="warning">{t("policies:page.cannotViewExistingPolicies")}</FormAlert> : (
                <>
                    {isError && data && (
                        <FormAlert status="warning">{t("policies:page.failedToRefreshPolicies")}</FormAlert>
                    )}
                    <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} className="mb-3" />
                    <div className="flex items-center justify-end mb-3 gap-2">
                        <ExpandCollapseAllButtons
                            onExpandAll={onExpandAll}
                            onCollapseAll={onCollapseAll}
                            expandDisabled={allOpen || !filteredPolicies?.length}
                            collapseDisabled={noneOpen}
                            className="flex items-center justify-end gap-2"
                        />
                    </div>
                    {isLoading ? <LoadingState message={t("ui_text:loading")} /> : isError ? (
                        <div className="flex flex-col items-center gap-3 py-10">
                            <p className="text-fg-muted">{t("policies:page.failedToLoadPolicies")}</p>
                            <Button onClick={refetch} variant="secondary">{t("ui_text:retry")}</Button>
                        </div>
                    ) : !filteredPolicies?.length ? (
                        <div className="flex flex-col items-center gap-3 py-10">
                            <ShieldOff size={32} aria-hidden="true" color="var(--fg-muted)" />
                            <p className="text-fg-muted">
                                {search ? t("policies:page.noPoliciesMatchSearch") : hasSearchOrFilters ? t("policies:page.noPoliciesMatchFilters") : t("policies:page.noPoliciesYet")}
                            </p>
                            {hasSearchOrFilters ? <Button onClick={onClearFilters} variant="secondary">{t("policies:page.clearSearchAndFilters")}</Button> : (
                                <IfCan action={PERMISSIONS.POLICIES_CREATE}>
                                    <Button variant="brand" onClick={onCreate}>{t("policies:page.createPolicy")}</Button>
                                </IfCan>
                            )}
                        </div>
                    ) : (
                        <div className="flex flex-col gap-5">
                            {groupedByResourceType.map(([resourceTypeName, policies]) => (
                                <div key={resourceTypeName}>
                                <h3 className="text-xs font-semibold text-fg-muted uppercase tracking-wide mb-2">{formatResourceTypeLabel(resourceTypeName)} ({policies.length})</h3>
                                    <div className="flex flex-col gap-2">{policies.map(renderCard)}</div>
                                </div>
                            ))}
                        </div>
                    )}
                    <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} className="mt-4" />
                </>
            )}

            <PolicyDetailsDialog
                isOpen={!!viewingPolicy}
                policy={viewingPolicy}
                triggerElement={viewingPolicyTrigger}
                onClose={() => onView(null)}
                onEdit={onEdit}
                isSaving={isSaving}
                errorMessage={formError}
                onSubmit={onSubmit}
                onActionsChange={onActionsChange}
                onFormClose={() => {
                    onCloseForm();
                    onView(null);
                }}
                initialTab={initialPolicyTab}
            />
            <PolicyFormDialog
                isOpen={formOpen && !editingPolicy}
                policy={editingPolicy}
                isSaving={isSaving}
                errorMessage={formError}
                onSubmit={onSubmit}
                onClose={onCloseForm}
                onDetails={() => {
                    onCloseForm();
                    onView(editingPolicy ?? null);
                }}
            />
            <ConfirmDialog
                isOpen={!!deletingPolicy}
                title={t("policies:page.deleteDialogTitle")}
                description={isDeletingPolicyHoldersLoading
                    ? t("policies:page.deleteDialogLoadingHolders", { policyName: deletingPolicy?.name })
                    : isDeletingPolicyHoldersError
                        ? t("policies:page.deleteDialogHoldersError")
                        : deletingPolicyHolders?.length
                            ? `${t("policies:page.deleteDialogDescription", { policyName: deletingPolicy?.name })} ${t("policies:page.deleteDialogHolderNote", { count: deletingPolicyHolders.length })}`
                            : t("policies:page.deleteDialogDescription", { policyName: deletingPolicy?.name })}
                confirmLabel={t("ui_text:delete")}
                isLoading={isDeletePending}
                confirmDisabled={isDeletingPolicyHoldersLoading || isDeletingPolicyHoldersError}
                onRetry={isDeletingPolicyHoldersError ? refetchDeletingPolicyHolders : undefined}
                retryLabel={t("ui_text:retry")}
                onConfirm={onConfirmDelete}
                onCancel={() => onDeleteRequest(null)}
            />
        </PageContainer>
    );
};

export default PoliciesPageContent;
