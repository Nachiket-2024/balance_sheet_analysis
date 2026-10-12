import type { TFunction } from "i18next";

import { toaster } from "../ui/toaster/toasterInstance";
import { formatPolicyActionLabel } from "./policyCardHelpers";
import type { useUpdatePolicyMutation } from "./queries/policyMutations";
import type { PolicyRead } from "../api/policies_api";

// Toast-wiring handlers for PoliciesPage.tsx's two undo-capable mutations
// (per-action toggle, activate/deactivate), split out to keep that file
// under the repo's ~350-line target, see AGENTS.md.

type UpdatePolicyMutation = ReturnType<typeof useUpdatePolicyMutation>;

export function handleActionsChange(params: {
    editingPolicy: PolicyRead | undefined;
    actions: string[];
    rollback: () => void;
    previousActions: string[];
    apply: () => void;
    t: TFunction;
    actionUpdateMutation: UpdatePolicyMutation;
}) {
    const { editingPolicy, actions, rollback, previousActions, apply, t, actionUpdateMutation } = params;
    if (!editingPolicy) return;
    const grantedAction = actions.find((action) => !previousActions.includes(action));
    const revokedAction = previousActions.find((action) => !actions.includes(action));
    const changedAction = grantedAction ?? revokedAction;
    const isGrant = !!grantedAction;
    const actionLabel = changedAction ? formatPolicyActionLabel(changedAction) : undefined;
    actionUpdateMutation.mutate(
        { policyName: editingPolicy.name, payload: { actions } },
        {
            onSuccess: () => {
                toaster.create({
                    title: t(isGrant ? "policies:page.policyActionGrantedToast" : "policies:page.policyActionRevokedToast", {
                        action: actionLabel ?? t("policies:page.policyActions"),
                        policyName: editingPolicy.name,
                    }),
                    type: "success",
                    duration: 6000,
                    action: {
                        label: t("policies:page.undo"),
                        onClick: () => {
                            rollback();
                            actionUpdateMutation.mutate(
                                { policyName: editingPolicy.name, payload: { actions: previousActions } },
                                {
                                    onSuccess: () => toaster.create({
                                        title: t(isGrant ? "policies:page.policyActionRevokedToast" : "policies:page.policyActionGrantedToast", {
                                            action: actionLabel ?? t("policies:page.policyActions"),
                                            policyName: editingPolicy.name,
                                        }),
                                        type: "success",
                                    }),
                                    onError: (error) => {
                                        apply();
                                        toaster.create({ title: error.message, type: "error" });
                                    },
                                },
                            );
                        },
                    },
                });
            },
            onError: (error) => {
                rollback();
                toaster.create({ title: error.message, type: "error" });
            },
        },
    );
}

// Activating/deactivating applies instantly and offers a 6s Undo instead of
// a confirm dialog first, per design/policies.html: it's fully reversible
// (unlike Delete), so a blocking confirmation was just an extra click for
// no safety benefit.
export function handleToggleActive(params: {
    policy: PolicyRead;
    t: TFunction;
    statusMutation: UpdatePolicyMutation;
    onError?: () => void;
}) {
    const { policy, t, statusMutation, onError } = params;
    const nextActive = !policy.is_active;
    statusMutation.mutate(
        { policyName: policy.name, payload: { is_active: nextActive } },
        {
            onSuccess: () => {
                toaster.create({
                    title: nextActive ? t("policies:page.policyReactivatedToast") : t("policies:page.policyDeactivatedToast"),
                    type: "success",
                    duration: 6000,
                    action: {
                        label: t("policies:page.undo"),
                        onClick: () => statusMutation.mutate(
                            { policyName: policy.name, payload: { is_active: !nextActive } },
                            {
                                onSuccess: () => toaster.create({
                                    title: nextActive ? t("policies:page.policyDeactivatedToast") : t("policies:page.policyReactivatedToast"),
                                    type: "success",
                                }),
                                onError: (error) => toaster.create({ title: error.message, type: "error" }),
                            },
                        ),
                    },
                });
            },
            onError: (error) => {
                onError?.();
                toaster.create({ title: error.message, type: "error" });
            },
        },
    );
}
