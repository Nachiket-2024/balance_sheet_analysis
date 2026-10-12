import type {
  useAssignPolicyMutation,
  useRevokePolicyMutation,
  useRevokePolicyActionMutation,
} from "../../policies/queries/policyMutations";
import type {
  useGrantPermissionMutation,
  useRevokePermissionMutation,
} from "../../policies/queries/permissionMutations";
import { toaster } from "../../ui/toaster/toasterInstance";

// Toast-wiring mutation handlers for useUserAccessDialogState.ts: assign/
// revoke a whole policy, revoke one action from a policy, grant/revoke a
// direct permission, and save a direct grant's conditions. Pure functions
// taking their mutations and inputs explicitly (no hook state of their own)
// so useUserAccessDialogState.ts stays the thin state/query layer that
// calls them - split out of one 455-line file, see AGENTS.md's ~350-line
// target.

type Translate = (key: string, options?: Record<string, unknown>) => string;
type AssignPolicyMutation = ReturnType<typeof useAssignPolicyMutation>;
type RevokePolicyMutation = ReturnType<typeof useRevokePolicyMutation>;
type RevokePolicyActionMutation = ReturnType<typeof useRevokePolicyActionMutation>;
type GrantPermissionMutation = ReturnType<typeof useGrantPermissionMutation>;
type RevokePermissionMutation = ReturnType<typeof useRevokePermissionMutation>;

export function togglePolicy(params: {
  userEmail: string | null;
  policyName: string;
  wasAssigned: boolean;
  t: Translate;
  assignMutation: AssignPolicyMutation;
  revokeMutation: RevokePolicyMutation;
}) {
  const { userEmail, policyName, wasAssigned, t, assignMutation, revokeMutation } = params;
  if (!userEmail) return;

  if (wasAssigned) {
    revokeMutation.mutate(
      { userEmail, policyName },
      {
        onSuccess: () =>
          toaster.create({
            title: t("users:accessDialog.policyRevokedToast", { policyName }),
            type: "info",
            action: {
              label: t("users:accessDialog.undo"),
              onClick: () =>
                assignMutation.mutate(
                  { userEmail, policyName },
                  {
                    onSuccess: () =>
                      toaster.create({
                        title: t("users:accessDialog.policyAssignedToast", {
                          policyName,
                        }),
                        type: "success",
                      }),
                    onError: (error) =>
                      toaster.create({ title: error.message, type: "error" }),
                  },
                ),
            },
          }),
        onError: (error) =>
          toaster.create({ title: error.message, type: "error" }),
      },
    );
  } else {
    assignMutation.mutate(
      { userEmail, policyName },
      {
        onSuccess: () =>
          toaster.create({
            title: t("users:accessDialog.policyAssignedToast", {
              policyName,
            }),
            type: "success",
            action: {
              label: t("users:accessDialog.undo"),
              onClick: () =>
                revokeMutation.mutate(
                  { userEmail, policyName },
                  {
                    onSuccess: () =>
                      toaster.create({
                        title: t("users:accessDialog.policyRevokedToast", {
                          policyName,
                        }),
                        type: "success",
                      }),
                    onError: (error) =>
                      toaster.create({ title: error.message, type: "error" }),
                  },
                ),
            },
          }),
        onError: (error) =>
          toaster.create({ title: error.message, type: "error" }),
      },
    );
  }
}

export function requestRevokePolicyAction(params: {
  userEmail: string | null;
  policyName: string;
  action: string;
  t: Translate;
  revokeActionMutation: RevokePolicyActionMutation;
}) {
  const { userEmail, policyName, action, t, revokeActionMutation } = params;
  if (!userEmail) return;
  revokeActionMutation.mutate(
    { userEmail, policyName, action },
    {
      onSuccess: () =>
        toaster.create({
          title: t("users:policiesDialog.actionRevokedToast", {
            action,
            policyName,
          }),
          type: "success",
        }),
      onError: (error) =>
        toaster.create({ title: error.message, type: "error" }),
    },
  );
}

/** Direct-grant toggle. The backend performs the privilege-escalation
 * check, so every authorized row uses one click and reports the result
 * immediately instead of adding a second confirmation state. */
export function toggleDirectPermission(params: {
  userEmail: string | null;
  action: string;
  resourceType: string;
  currentGrant: { conditions?: Record<string, unknown> | null } | undefined;
  t: Translate;
  grantMutation: GrantPermissionMutation;
  revokePermissionMutation: RevokePermissionMutation;
}) {
  const { userEmail, action, resourceType, currentGrant, t, grantMutation, revokePermissionMutation } = params;
  if (!userEmail) return;

  if (currentGrant) {
    const pendingToastId = toaster.create({
      title: t("users:accessDialog.permissionRevokingToast", { action }),
      type: "loading",
      duration: Infinity,
    });
    revokePermissionMutation.mutate(
      { userEmail, action, resourceType },
      {
        onSuccess: () =>
          toaster.update(pendingToastId, {
            title: t("users:accessDialog.permissionRevokedToast", { action }),
            type: "info",
            action: {
              label: t("users:accessDialog.undo"),
              onClick: () =>
                grantMutation.mutate(
                  {
                    userEmail,
                    action,
                    resource_type: resourceType,
                    conditions: currentGrant.conditions ?? undefined,
                  },
                  {
                    onSuccess: () =>
                      toaster.create({
                        title: t(
                          "users:accessDialog.permissionGrantedToast",
                          { action },
                        ),
                        type: "success",
                      }),
                    onError: (error) =>
                      toaster.create({ title: error.message, type: "error" }),
                  },
                ),
            },
          }),
        onError: (error) =>
          (() => {
            toaster.dismiss(pendingToastId);
            toaster.create({ title: error.message, type: "error", duration: 8000 });
          })(),
      },
    );
    return;
  }

  const pendingToastId = toaster.create({
    title: t("users:accessDialog.permissionGrantingToast", { action }),
    type: "loading",
    duration: Infinity,
  });
  grantMutation.mutate(
    { userEmail, action, resource_type: resourceType },
    {
      onSuccess: () =>
        toaster.update(pendingToastId, {
          title: t("users:accessDialog.permissionGrantedToast", { action }),
          type: "success",
          action: {
            label: t("users:accessDialog.undo"),
            onClick: () =>
              revokePermissionMutation.mutate(
                { userEmail, action, resourceType },
                {
                  onSuccess: () =>
                    toaster.create({
                      title: t("users:accessDialog.permissionRevokedToast", {
                        action,
                      }),
                      type: "success",
                    }),
                  onError: (error) =>
                    toaster.create({ title: error.message, type: "error" }),
                },
              ),
          },
        }),
      onError: (error) =>
        (() => {
          toaster.dismiss(pendingToastId);
          toaster.create({ title: error.message, type: "error", duration: 8000 });
        })(),
    },
  );
}

export function saveConditions(params: {
  userEmail: string | null;
  action: string;
  resourceType: string;
  conditionsText: string;
  t: Translate;
  grantMutation: GrantPermissionMutation;
  onSaved: () => void;
}): string | null {
  const { userEmail, action, resourceType, conditionsText, t, grantMutation, onSaved } = params;
  if (!userEmail) return null;
  let conditions: Record<string, unknown> | undefined;
  if (conditionsText.trim()) {
    try {
      conditions = JSON.parse(conditionsText);
    } catch {
      return t("users:permissionsDialog.invalidConditionsJson");
    }
  }
  grantMutation.mutate(
    { userEmail, action, resource_type: resourceType, conditions },
    {
      onSuccess: () => {
        toaster.create({
          title: t("users:accessDialog.conditionsSavedToast", { action }),
          type: "success",
        });
        onSaved();
      },
      onError: (error) =>
        toaster.create({ title: error.message, type: "error" }),
    },
  );
  return null;
}
