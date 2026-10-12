import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  useUserPoliciesQuery,
  useMyPoliciesQuery,
  usePoliciesQuery,
} from "../../policies/queries/policyQueries";
import {
  useUserPermissionsQuery,
  useMyPermissionsQuery,
  usePermissionCatalogQuery,
} from "../../policies/queries/permissionQueries";
import {
  useAssignPolicyMutation,
  useRevokePolicyMutation,
  useRevokePolicyActionMutation,
} from "../../policies/queries/policyMutations";
import {
  useGrantPermissionMutation,
  useRevokePermissionMutation,
} from "../../policies/queries/permissionMutations";
import {
  buildEffectiveGrantKeySet,
  isAlreadyEffectivelyGranted,
} from "../../policies/logic/effectiveGrants";
import { useAuthStore } from "../../store/authStore";
import { useCan } from "../../authorization/useCan";
import { PERMISSIONS } from "../../authorization/permissions";
import {
  getMySecurityAuditLogApi,
  getUserSecurityAuditLogApi,
} from "../../api/audit_api";
import * as handlers from "./userAccessDialogHandlers";

/** How many "Recent access changes" rows the Details tab shows - enough to
 * be useful without turning a stat-tile summary tab into a second audit
 * log; "View all" links to the real one for anything beyond this. */
const RECENT_ACCESS_CHANGES_LIMIT = 5;

export type AccessDialogTab = "details" | "policies" | "permissions";
export type AccessFilter = "all" | "on" | "off";

/**
 * useUserAccessDialogState
 * ----------------------------
 * All query selection, mutation wiring, and toggle/undo handlers behind
 * UserAccessDialog's unified Details/Policies/Permissions tabs. Replaces the
 * separate useUserPoliciesDialogState + the inline state UserPermissionsDialog
 * used to carry, per design/user-access.html and
 * .project/user-access-dialog-review.md.
 *
 * Toast-wiring for each mutation (assign/revoke a policy, revoke one policy
 * action, grant/revoke a direct permission, save conditions) lives in
 * userAccessDialogHandlers.ts as plain functions; this hook stays the state/
 * query layer that calls them.
 *
 * Two different undo shapes, because the backend only supports two of the
 * three edits both ways:
 * - Whole-policy assign/revoke and direct-permission grant/revoke are both
 *   fully reversible API calls (assign <-> revoke, grant <-> revoke), so
 *   both get an instant toggle with a real Undo toast.
 * - Revoking one action from an otherwise-still-assigned policy
 *   (revokePolicyActionApi) has no inverse endpoint - re-assigning the whole
 *   policy would restore every other action already revoked from it, not
 *   just this one. It is therefore an immediate one-way toggle, with no
 *   misleading Undo action or extra confirmation dialog.
 */
export function useUserAccessDialogState(
  isOpen: boolean,
  userEmail: string | null,
  initialTab: AccessDialogTab = "details",
) {
  const { t } = useTranslation(["users", "ui_text"]);
  const currentUserEmail = useAuthStore((s) => s.email);
  const isSelf = !!userEmail && userEmail === currentUserEmail;

  const [tab, setTab] = useState<AccessDialogTab>("details");
  const [polQuery, setPolQuery] = useState("");
  const [polFilter, setPolFilter] = useState<AccessFilter>("all");
  const [polOpen, setPolOpen] = useState<Set<string>>(new Set());
  const [permQuery, setPermQuery] = useState("");
  const [permFilter, setPermFilter] = useState<AccessFilter>("all");
  const [permClosedGroups, setPermClosedGroups] = useState<Set<string>>(
    new Set(),
  );
  const [editingKey, setEditingKey] = useState<string | null>(null);

  // Reset on every open, adjusted during render (same pattern as the
  // dialogs this replaces): tab starts on whichever tab the row icon that
  // opened the dialog points at (View->Details, Policies->Policies,
  // Permissions->Permissions), defaulting to Details - matching the first
  // mockup review's "opened on the last tab" fix.
  const [prevIsOpen, setPrevIsOpen] = useState(isOpen);
  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (isOpen) {
      setTab(initialTab);
      setPolQuery("");
      setPolFilter("all");
      setPolOpen(new Set());
      setPermQuery("");
      setPermFilter("all");
      setPermClosedGroups(new Set());
      setEditingKey(null);
    }
  }

  // Own row uses the self-service /me endpoints regardless of holding
  // policies:read/permissions:read, same reasoning as the three dialogs
  // this merges (see their docstrings for why).
  const managementPoliciesQuery = useUserPoliciesQuery(
    userEmail ?? "",
    isOpen && !!userEmail && !isSelf,
  );
  const myPoliciesQuery = useMyPoliciesQuery(isOpen && isSelf);
  const userPoliciesQuery = isSelf ? myPoliciesQuery : managementPoliciesQuery;

  const managementPermissionsQuery = useUserPermissionsQuery(
    userEmail ?? "",
    isOpen && !!userEmail && !isSelf,
  );
  const myPermissionsQuery = useMyPermissionsQuery(isOpen && isSelf);
  const userPermissionsQuery = isSelf
    ? myPermissionsQuery
    : managementPermissionsQuery;

  const allPoliciesQuery = usePoliciesQuery(isOpen);
  const catalogQuery = usePermissionCatalogQuery(isOpen);

  // "Recent access changes" (Details tab): own row uses /me (no permission
  // required, same self-service reasoning as the policies/permissions
  // queries above); another user's row needs security_audit:read, and the
  // query stays disabled without it rather than firing a request that can
  // only 403 - the section itself is simply omitted (see UserAccessDialog).
  const canReadSecurityAudit = useCan(PERMISSIONS.SECURITY_AUDIT_READ);
  const recentAccessChangesQuery = useQuery({
    queryKey: ["auditLog", "security", "accessChanges", userEmail, isSelf],
    queryFn: async () =>
      isSelf
        ? (
            await getMySecurityAuditLogApi({
              eventType: "access_change",
              limit: RECENT_ACCESS_CHANGES_LIMIT,
            })
          ).data
        : (
            await getUserSecurityAuditLogApi(userEmail ?? "", {
              eventType: "access_change",
              limit: RECENT_ACCESS_CHANGES_LIMIT,
            })
          ).data,
    enabled: isOpen && !!userEmail && (isSelf || canReadSecurityAudit),
  });

  const assignMutation = useAssignPolicyMutation();
  const revokeMutation = useRevokePolicyMutation();
  const revokeActionMutation = useRevokePolicyActionMutation();
  const grantMutation = useGrantPermissionMutation();
  const revokePermissionMutation = useRevokePermissionMutation();

  const assignedPolicies = userPoliciesQuery.data?.policies ?? [];
  const assignedNames = new Set(assignedPolicies.map((p) => p.name));
  const directGrants = userPermissionsQuery.data?.permissions ?? [];
  const effectiveGrantKeys = buildEffectiveGrantKeySet(
    assignedPolicies,
    directGrants,
  );

  const armKey = (action: string, resourceType: string) =>
    `${action}::${resourceType}`;

  function togglePolicy(policyName: string) {
    handlers.togglePolicy({
      userEmail,
      policyName,
      wasAssigned: assignedNames.has(policyName),
      t,
      assignMutation,
      revokeMutation,
    });
  }

  function requestRevokePolicyAction(policyName: string, action: string) {
    handlers.requestRevokePolicyAction({
      userEmail,
      policyName,
      action,
      t,
      revokeActionMutation,
    });
  }

  function toggleDirectPermission(action: string, resourceType: string) {
    const currentGrant = directGrants.find(
      (g) => g.action === action && g.resource_type === resourceType,
    );
    handlers.toggleDirectPermission({
      userEmail,
      action,
      resourceType,
      currentGrant,
      t,
      grantMutation,
      revokePermissionMutation,
    });
  }

  function saveConditions(
    action: string,
    resourceType: string,
    conditionsText: string,
  ): string | null {
    return handlers.saveConditions({
      userEmail,
      action,
      resourceType,
      conditionsText,
      t,
      grantMutation,
      onSaved: () => setEditingKey(null),
    });
  }

  const togglePolicyOpen = (policyName: string) =>
    setPolOpen((prev) => {
      const next = new Set(prev);
      if (next.has(policyName)) next.delete(policyName);
      else next.add(policyName);
      return next;
    });
  const expandAllPolicies = () =>
    setPolOpen(new Set(allPoliciesQuery.data?.map((p) => p.name) ?? []));
  const collapseAllPolicies = () => setPolOpen(new Set());

  const togglePermGroup = (resourceType: string) =>
    setPermClosedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(resourceType)) next.delete(resourceType);
      else next.add(resourceType);
      return next;
    });
  const expandAllPermGroups = () => setPermClosedGroups(new Set());
  const collapseAllPermGroups = () =>
    setPermClosedGroups(
      new Set((catalogQuery.data ?? []).map((e) => e.resource_type)),
    );

  return {
    t,
    isSelf,
    tab,
    setTab,
    polQuery,
    setPolQuery,
    polFilter,
    setPolFilter,
    polOpen,
    togglePolicyOpen,
    expandAllPolicies,
    collapseAllPolicies,
    permQuery,
    setPermQuery,
    permFilter,
    setPermFilter,
    permClosedGroups,
    togglePermGroup,
    expandAllPermGroups,
    collapseAllPermGroups,
    armKey,
    editingKey,
    setEditingKey,
    userPoliciesQuery,
    userPermissionsQuery,
    allPoliciesQuery,
    catalogQuery,
    canReadSecurityAudit,
    recentAccessChangesQuery,
    assignedPolicies,
    assignedNames,
    directGrants,
    effectiveGrantKeys,
    isAlreadyEffectivelyGranted,
    togglePolicy,
    requestRevokePolicyAction,
    toggleDirectPermission,
    saveConditions,
    assignMutation,
    revokeMutation,
    revokeActionMutation,
    grantMutation,
    revokePermissionMutation,
  };
}
