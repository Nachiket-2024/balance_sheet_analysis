import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";
import { useCan } from "../authorization/useCan";
import { PERMISSIONS } from "../authorization/permissions";
import { useDebouncedValue } from "../ui/hooks/useDebouncedValue";
import { usePageResetOn } from "../ui/hooks/usePageResetOn";
import { toaster } from "../ui/toaster/toasterInstance";
import { usePoliciesQuery, usePoliciesListQuery, usePolicyHoldersQuery } from "./queries/policyQueries";
import { useCreatePolicyMutation, useUpdatePolicyMutation, useDeletePolicyMutation } from "./queries/policyMutations";
import type { PolicyFormValues } from "./dialogs/PolicyFormDialog";
import { ALL_VALUE } from "./PoliciesFilterBar";
import type { PolicyRead } from "../api/policies_api";
import { usePoliciesUiStore } from "./policiesUiStore";
import PoliciesPageContent from "./PoliciesPageContent";
import { groupPoliciesByResourceType } from "./policyListHelpers";
import * as pageHandlers from "./policiesPageHandlers";
import { useOptimisticPolicyActivity } from "./useOptimisticPolicyActivity";

const PAGE_SIZE = 25;

/** Maps the placeholder "All" option ("") to `undefined` (no filter). */
function toBoolFilter(value: string): boolean | undefined {
    if (value === ALL_VALUE) return undefined;
    return value === "true";
}

/**
 * PoliciesPage
 * ----------------------------
 * Management CRUD for policies (backend: /authorization/policies). The
 * route is gated by ProtectedRoute on policies:read or policies:create;
 * create/edit/delete are further gated per-action via IfCan since a caller
 * might have read without create/update/delete. Search and resource-type/
 * status filters run server-side (same as UsersPage) since the policy list
 * can no longer be assumed small enough to filter client-side.
 *
 * Renders one card per policy (design/policies.html), not a table: at
 * dozens of policies and hundreds of actions, a table row of badges became
 * a wall of text. Each card collapses its actions by default and expands
 * to show them grouped by verb. Activating/deactivating is an instant
 * switch with a 6s Undo toast instead of a confirm dialog, since it's
 * fully reversible; only Delete keeps a confirmation.
 *
 * A caller with only policies:create (not policies:read) can't list, search,
 * or filter policies, since GET /authorization/policies requires read. For
 * them the list/stats queries never fire (see canReadPolicies below) and the
 * page shows a restricted-view notice plus a standalone Create Policy
 * button instead of an empty list stuck in an error state.
 */
const PoliciesPage: React.FC = () => {
    const { t } = useTranslation(["policies", "ui_text"]);

    const canReadPolicies = useCan(PERMISSIONS.POLICIES_READ);

    const [searchParams] = useSearchParams();
    const policyUiStore = usePoliciesUiStore();
    // Search accepts a one-shot URL override for command-palette and external
    // deep links. Other filters remain session-persisted, matching Users and
    // Permissions, because they represent operator workspace preferences.
    const [search, setSearchState] = useState(() => searchParams.get("search") ?? policyUiStore.search);
    const { resourceType, status, containsAction, destructiveOnly, update } = policyUiStore;
    const setSearch = (value: string) => {
        setSearchState(value);
        update({ search: value });
    };
    // Debounced since search is now a server request, not a client filter -
    // typing shouldn't fire one request per keystroke.
    const debouncedSearch = useDebouncedValue(search);
    const setResourceType = (value: string) => update({ resourceType: value });
    const setStatus = (value: string) => update({ status: value });
    const setContainsAction = (value: string) => update({ containsAction: value });
    // Which stats tile (if any) drives the current status filter, purely to
    // decide which tile renders pressed - "destructive" has no server-side
    // filter param, so it's applied client-side below instead of joining
    // this piece of state.
    const setDestructiveOnly = (value: boolean | ((prev: boolean) => boolean)) =>
        update({ destructiveOnly: typeof value === "function" ? value(destructiveOnly) : value });

    // Any search/filter change can make the current page meaningless, so
    // always reset to page 1. See usePageResetOn's docstring for why this
    // is derived during render rather than in an effect.
    const [page, setPage] = usePageResetOn(
        `${debouncedSearch}|${resourceType}|${status}|${containsAction}|${destructiveOnly}`
    );

    const { data, isFetching, isLoading, isError, refetch } = usePoliciesListQuery(
        page,
        PAGE_SIZE,
        {
            search: debouncedSearch,
            resourceType: resourceType || undefined,
            isActive: toBoolFilter(status),
            containsAction: containsAction || undefined,
            destructiveOnly,
            sortBy: "name",
            sortDir: "asc",
        },
        canReadPolicies
    );
    // PolicyStatsCard's counts should stay independent of the current page/
    // filters, so it uses the full unfiltered list.
    const {
        data: allPolicies,
        isLoading: isStatsLoading,
    } = usePoliciesQuery(canReadPolicies);

    const serverPolicies = data?.policies;
    const { policies: filteredPolicies, setOptimisticActive, rollbackOptimisticActive } = useOptimisticPolicyActivity(serverPolicies);
    const displayTotal = data?.total;
    const displayData = data && displayTotal !== undefined
        ? { policies: filteredPolicies ?? [], total: displayTotal }
        : data;
    const displayIsLoading = isLoading;
    const displayIsError = isError && !data;
    const displayRefetch = refetch;
    const totalPages = displayTotal !== undefined ? Math.max(1, Math.ceil(displayTotal / PAGE_SIZE)) : 1;

    // Policies are always grouped by resource type. Rows within a group keep
    // the server's own name-sort order and show the group count.
    const groupedByResourceType = useMemo(
        () => groupPoliciesByResourceType(filteredPolicies ?? []),
        [filteredPolicies],
    );

    const [formOpen, setFormOpen] = useState(false);
    const [editingPolicy, setEditingPolicy] = useState<PolicyRead | undefined>(undefined);
    const [deletingPolicy, setDeletingPolicy] = useState<PolicyRead | null>(null);
    const [viewingPolicy, setViewingPolicy] = useState<PolicyRead | null>(null);
    const [viewingPolicyTrigger, setViewingPolicyTrigger] = useState<HTMLElement | null>(null);
    const [initialPolicyTab, setInitialPolicyTab] = useState<"details" | "edit">("details");
    const [openNames, setOpenNames] = useState<Set<string>>(new Set());

    // Fetched only once the delete confirm is actually open, to show "N
    // users will lose access" (design/policies.html's deleteNote) instead
    // of the generic warning alone.
    const {
        data: deletingPolicyHolders,
        isLoading: isDeletingPolicyHoldersLoading,
        isError: isDeletingPolicyHoldersError,
        refetch: refetchDeletingPolicyHolders,
    } = usePolicyHoldersQuery(deletingPolicy?.name ?? "", !!deletingPolicy);

    const createMutation = useCreatePolicyMutation();
    const updateMutation = useUpdatePolicyMutation();
    const actionUpdateMutation = useUpdatePolicyMutation();
    const deleteMutation = useDeletePolicyMutation();
    // Separate from updateMutation (the edit form's own save call) so a
    // switch click's pending state doesn't bleed into PolicyFormDialog's
    // isSaving.
    const statusMutation = useUpdatePolicyMutation();
    const togglingName = statusMutation.isPending ? statusMutation.variables?.policyName : undefined;

    const openCreateForm = () => {
        setEditingPolicy(undefined);
        setViewingPolicy(null);
        setViewingPolicyTrigger(null);
        setFormOpen(true);
    };

    const openEditForm = (policy: PolicyRead) => {
        setEditingPolicy(policy);
        setInitialPolicyTab("edit");
        setViewingPolicy(policy);
        setFormOpen(false);
    };

    const openView = (policy: PolicyRead | null, trigger?: HTMLElement) => {
        if (policy) {
            setEditingPolicy(policy);
            setInitialPolicyTab("details");
            if (trigger) setViewingPolicyTrigger(trigger);
        }
        setViewingPolicy(policy);
    };

    const closeForm = () => {
        setFormOpen(false);
        createMutation.reset();
        updateMutation.reset();
    };

    const handleFormSubmit = (values: PolicyFormValues) => {
        if (editingPolicy) {
            updateMutation.mutate(
                { policyName: editingPolicy.name, payload: values },
                {
                    onSuccess: () => {
                        toaster.create({ title: t("policies:page.policyUpdatedToast"), type: "success" });
                        closeForm();
                        setViewingPolicy(null);
                    },
                }
            );
        } else {
            createMutation.mutate(values, {
                onSuccess: () => {
                    toaster.create({ title: t("policies:page.policyCreatedToast"), type: "success" });
                    closeForm();
                },
            });
        }
    };

    const handleActionsChange = (
        actions: string[],
        rollback: () => void,
        previousActions: string[],
        apply: () => void,
    ) => pageHandlers.handleActionsChange({ editingPolicy, actions, rollback, previousActions, apply, t, actionUpdateMutation });

    const handleDeleteConfirm = () => {
        if (!deletingPolicy) return;
        deleteMutation.mutate(
            { policyName: deletingPolicy.name },
            {
                onSuccess: () => {
                    toaster.create({ title: t("policies:page.policyDeletedToast"), type: "success" });
                    setDeletingPolicy(null);
                },
                onError: (error) => {
                    toaster.create({ title: error.message, type: "error" });
                },
            }
        );
    };

    const handleToggleActive = (policy: PolicyRead) => {
        const nextActive = !policy.is_active;
        setOptimisticActive(policy, nextActive);
        pageHandlers.handleToggleActive({
            policy,
            t,
            statusMutation,
            onError: () => rollbackOptimisticActive(policy.name),
        });
    };

    const toggleOpen = (policyName: string) => {
        setOpenNames((prev) => {
            const next = new Set(prev);
            if (next.has(policyName)) next.delete(policyName);
            else next.add(policyName);
            return next;
        });
    };
    const expandAll = () => setOpenNames(new Set((filteredPolicies ?? []).map((p) => p.name)));
    const collapseAll = () => setOpenNames(new Set());
    const allOpen = !!filteredPolicies?.length && filteredPolicies.every((p) => openNames.has(p.name));
    const noneOpen = openNames.size === 0;

    const hasSearchOrFilters =
        !!search || resourceType !== ALL_VALUE || status !== ALL_VALUE || containsAction !== ALL_VALUE || destructiveOnly;
    const clearAllFilters = () => {
        setSearch("");
        setResourceType(ALL_VALUE);
        setStatus(ALL_VALUE);
        setContainsAction(ALL_VALUE);
        setDestructiveOnly(false);
    };

    const activeTile = destructiveOnly
        ? "destructive"
        : status === "true" && resourceType === ALL_VALUE && !search
          ? "active"
          : status === "false" && resourceType === ALL_VALUE && !search
            ? "inactive"
            : !hasSearchOrFilters
              ? "total"
              : null;

    return <PoliciesPageContent
        canReadPolicies={canReadPolicies}
        data={displayData}
        allPolicies={allPolicies}
        isStatsLoading={isStatsLoading}
        isFetching={isFetching}
        isLoading={displayIsLoading}
        isError={displayIsError}
        refetch={displayRefetch}
        page={page}
        totalPages={totalPages}
        filteredPolicies={filteredPolicies}
        groupedByResourceType={groupedByResourceType}
        search={search}
        resourceType={resourceType}
        status={status}
        containsAction={containsAction}
        destructiveOnly={destructiveOnly}
        hasSearchOrFilters={hasSearchOrFilters}
        activeTile={activeTile}
        openNames={openNames}
        togglingName={togglingName}
        deletingPolicy={deletingPolicy}
        deletingPolicyHolders={deletingPolicyHolders}
        isDeletingPolicyHoldersLoading={isDeletingPolicyHoldersLoading}
        isDeletingPolicyHoldersError={isDeletingPolicyHoldersError}
        refetchDeletingPolicyHolders={refetchDeletingPolicyHolders}
        editingPolicy={editingPolicy}
        viewingPolicy={viewingPolicy}
        viewingPolicyTrigger={viewingPolicyTrigger}
        initialPolicyTab={initialPolicyTab}
        formOpen={formOpen}
        isSaving={createMutation.isPending || updateMutation.isPending}
        formError={createMutation.error?.message ?? updateMutation.error?.message ?? null}
        isDeletePending={deleteMutation.isPending}
        onPageChange={setPage}
        onSearchChange={setSearch}
        onResourceTypeChange={setResourceType}
        onStatusChange={setStatus}
        onContainsActionChange={setContainsAction}
        onDestructiveOnlyChange={setDestructiveOnly}
        onClearFilters={clearAllFilters}
        onExpandAll={expandAll}
        onCollapseAll={collapseAll}
        allOpen={allOpen}
        noneOpen={noneOpen}
        onCreate={openCreateForm}
        onEdit={openEditForm}
        onView={openView}
        onToggleOpen={toggleOpen}
        onToggleActive={handleToggleActive}
        onDeleteRequest={setDeletingPolicy}
        onSubmit={handleFormSubmit}
        onActionsChange={handleActionsChange}
        onCloseForm={closeForm}
        onConfirmDelete={handleDeleteConfirm}
    />;
};

export default PoliciesPage;
