/* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps -- dialog state resets follow its controlled open lifecycle. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Key, Shield, UserCog } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../../ui/shadcn/dialog";
import { Button } from "../../ui/buttons/Button";
import BulkOperationResultList from "./BulkOperationResultList";
import BulkPolicyTab from "./BulkPolicyTab";
import BulkPermissionTab from "./BulkPermissionTab";
import BulkRoleTab from "./BulkRoleTab";
import { useBulkAssignPoliciesMutation, useBulkRemovePoliciesMutation, useBulkAssignPermissionsMutation, useBulkRemovePermissionsMutation, useBulkUpdateRoleMutation } from "../../policies/queries/bulkAssignmentMutations";
import { usePoliciesQuery, useMyPoliciesQuery } from "../../policies/queries/policyQueries";
import { usePermissionCatalogQuery, useMyPermissionsQuery } from "../../policies/queries/permissionQueries";
import { buildEffectiveGrantKeySet, isAlreadyEffectivelyGranted, policyAddsNothingNew } from "../../policies/logic/effectiveGrants";
import { useAuthStore } from "../../store/authStore";
import { useAuthorization } from "../../authorization/useAuthorization";
import { canGrantAction, canGrantPolicy } from "../../authorization/grantability";
import { toaster } from "../../ui/toaster/toasterInstance";
import { cn } from "../../ui/styles/classNames";
import SearchInput from "../../ui/filters/SearchInput";
import { DIALOG_FOOTER_CLASSNAME, DIALOG_HEADER_CLASSNAME, DIALOG_PANEL_CLASSNAME } from "../../ui/styles/dialogStyles";

type BulkTab = "policies" | "permissions" | "roles";
interface Props { isOpen: boolean; userEmails: string[]; initialTab?: BulkTab; onClose: () => void; }

const BulkUserAccessDialog: React.FC<Props> = ({ isOpen, userEmails, initialTab = "policies", onClose }) => {
  const { t } = useTranslation(["users", "ui_text"]);
  const [tab, setTab] = useState<BulkTab>("policies");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [selectedUsersOpen, setSelectedUsersOpen] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);
  const [selectedUserSearch, setSelectedUserSearch] = useState("");
  const [selectedUserPage, setSelectedUserPage] = useState(1);
  const filteredSelectedUsers = useMemo(() => userEmails.filter((email) => email.toLowerCase().includes(selectedUserSearch.trim().toLowerCase())), [selectedUserSearch, userEmails]);
  const selectedUserPages = Math.max(1, Math.ceil(filteredSelectedUsers.length / 50));
  const visibleSelectedUsers = filteredSelectedUsers.slice((selectedUserPage - 1) * 50, selectedUserPage * 50);
  const [selectedPolicies, setSelectedPolicies] = useState<string[]>([]);
  const [policySearch, setPolicySearch] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [expandedPermissionGroups, setExpandedPermissionGroups] = useState<string[]>([]);
  const [conditions, setConditions] = useState("");
  const [role, setRole] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);
  const currentEmail = useAuthStore((state) => state.email);
  const { can } = useAuthorization();
  const policies = usePoliciesQuery(isOpen);
  const catalog = usePermissionCatalogQuery();
  const self = userEmails.length === 1 && userEmails[0] === currentEmail;
  const minePolicies = useMyPoliciesQuery(isOpen && self);
  const minePermissions = useMyPermissionsQuery(isOpen && self);
  const grants = self ? buildEffectiveGrantKeySet(minePolicies.data?.policies ?? [], minePermissions.data?.permissions ?? []) : null;
  const availablePolicies = (policies.data ?? []).filter((policy) =>
    canGrantPolicy(policy, can) && (!grants || !policyAddsNothingNew(policy, grants)),
  );
  const availablePermissions = (catalog.data ?? []).filter((permission) =>
    canGrantAction(permission.action, can) &&
    (!grants || !isAlreadyEffectivelyGranted(grants, permission.action, permission.resource_type)),
  );
  const permissionGroups = availablePermissions.reduce<Record<string, typeof availablePermissions>>((groups, entry) => { (groups[entry.resource_type] ??= []).push(entry); return groups; }, {});
  const assignPolicy = useBulkAssignPoliciesMutation();
  const removePolicy = useBulkRemovePoliciesMutation();
  const grantPermission = useBulkAssignPermissionsMutation();
  const revokePermission = useBulkRemovePermissionsMutation();
  const updateRole = useBulkUpdateRoleMutation();
  const result = lastAction === "assign-policy" ? assignPolicy.data : lastAction === "remove-policy" ? removePolicy.data : lastAction === "grant-permission" ? grantPermission.data : lastAction === "revoke-permission" ? revokePermission.data : updateRole.data;
  const resultOperationLabel = lastAction === "assign-policy"
    ? t("users:bulkActions.operationAssignPolicy", { value: selectedPolicies.join(", ") })
    : lastAction === "remove-policy"
      ? t("users:bulkActions.operationRemovePolicy", { value: selectedPolicies.join(", ") })
      : lastAction === "grant-permission"
        ? t("users:bulkActions.operationGrantPermission", { value: permissions.map((key) => key.split("::")[0]).join(", ") })
        : lastAction === "revoke-permission"
          ? t("users:bulkActions.operationRevokePermission", { value: permissions.map((key) => key.split("::")[0]).join(", ") })
          : t("users:bulkActions.operationSetRole", { value: role });

  useEffect(() => { if (isOpen) setTab(initialTab); }, [isOpen, initialTab]);
  // Initialize the groups once per dialog data lifecycle. A catalog refresh
  // must not reopen a group the permission holder deliberately collapsed while
  // selecting permissions.
  const initializedCatalogRef = useRef(false);
  useEffect(() => {
    if (!initializedCatalogRef.current && Object.keys(permissionGroups).length) {
      initializedCatalogRef.current = true;
      setExpandedPermissionGroups(Object.keys(permissionGroups));
    }
  }, [catalog.data, permissionGroups]);
  useEffect(() => {
    if (!isOpen) {
      setResultOpen(false); setLastAction(null);
      assignPolicy.reset(); removePolicy.reset(); grantPermission.reset(); revokePermission.reset(); updateRole.reset();
    }
  }, [isOpen]);
  // Keep the selection/configuration dialog intact and present the per-user
  // outcomes in a separate dialog. This gives permission holders a focused
  // report without losing the operation context underneath.
  useEffect(() => { if (result) setResultOpen(true); }, [result]);

  const reset = (next: BulkTab) => { setTab(next); setError(null); setLastAction(null); };
  const tabValues: BulkTab[] = ["policies", "permissions", "roles"];
  const activateTab = (next: BulkTab) => { reset(next); requestAnimationFrame(() => tabRefs.current[tabValues.indexOf(next)]?.focus()); };
  const parseConditions = (): Record<string, unknown> | undefined | false => {
    if (!conditions.trim()) return undefined;
    try { return JSON.parse(conditions); } catch { setError(t("users:permissionsDialog.invalidConditionsJson")); return false; }
  };
  const runPolicy = (remove: boolean) => {
    if (!selectedPolicies.length) return;
    setLastAction(remove ? "remove-policy" : "assign-policy");
    (remove ? removePolicy : assignPolicy).mutate({ userEmails, policyNames: selectedPolicies }, { onError: (err) => toaster.create({ title: err.message, type: "error" }) });
  };
  const runPermission = (remove: boolean) => {
    if (!permissions.length) return;
    const parsed = remove ? undefined : parseConditions();
    if (parsed === false) return;
    const actions = permissions.map((key) => { const [action, resourceType] = key.split("::"); return { action, resourceType }; });
    setLastAction(remove ? "revoke-permission" : "grant-permission");
    (remove ? revokePermission : grantPermission).mutate(remove ? { userEmails, actions } : { userEmails, actions, conditions: parsed }, { onError: (err) => toaster.create({ title: err.message, type: "error" }) });
  };
  const runRole = () => { if (!role) return; setLastAction("role"); updateRole.mutate({ userEmails, role }, { onError: (err) => toaster.create({ title: err.message, type: "error" }) }); };
  const tabs = [{ value: "policies" as const, label: t("users:accessDialog.tabPolicies"), icon: <Shield size={16} aria-hidden="true" /> }, { value: "permissions" as const, label: t("users:accessDialog.tabPermissions"), icon: <Key size={16} aria-hidden="true" /> }, { value: "roles" as const, label: t("users:bulkActions.setRole"), icon: <UserCog size={16} aria-hidden="true" /> }];

  return <>
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent overlayClassName="backdrop-blur-[2px]" closeLabel={t("ui_text:closeDialog")} className={cn("w-[calc(100vw-1.5rem)] sm:max-w-3xl lg:max-w-[55rem] h-[min(44rem,calc(100svh-1.5rem))] flex flex-col overflow-hidden", DIALOG_PANEL_CLASSNAME)}>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-5 sm:px-6 bg-bg-canvas/60">
          <div className="sticky top-0 z-30 flex items-center gap-2 bg-bg-canvas pb-2"><div role="tablist" className="flex min-w-0 flex-1 overflow-hidden rounded-lg border border-border-strong bg-bg-surface shadow-[0_1px_0_var(--border-strong)]" aria-label={t("users:accessDialog.tabPolicies")}>{tabs.map((item, index) => <button key={item.value} ref={(element) => { tabRefs.current[index] = element; }} type="button" role="tab" aria-selected={tab === item.value} tabIndex={tab === item.value ? 0 : -1} onClick={() => activateTab(item.value)} onKeyDown={(event) => { const current = tabValues.indexOf(item.value); const next = event.key === "ArrowRight" || event.key === "ArrowDown" ? (current + 1) % 3 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? (current + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : current; if (next !== current) { event.preventDefault(); activateTab(tabValues[next]); } }} className={cn("inline-flex h-10 min-w-0 flex-1 items-center justify-center gap-2 whitespace-nowrap px-3 text-base font-semibold transition-colors", index > 0 && "border-l border-border-strong", tab === item.value ? "bg-brand-tile-subtle text-brand-fg shadow-[inset_0_0_0_2px_var(--brand-solid)]" : "text-fg-muted hover:bg-brand-subtle hover:text-brand-fg")}>{item.icon}{item.label}</button>)}</div></div>
          <DialogHeader className={cn(DIALOG_HEADER_CLASSNAME, "sticky top-11 z-20 -mx-5 mt-1 bg-bg-canvas px-5 sm:-mx-6 sm:px-6")}><div className="flex items-center gap-3"><div className="grid size-10 shrink-0 place-items-center rounded-full border border-[var(--brand-400)] bg-brand-subtle text-brand-fg"><UserCog size={18} aria-hidden="true" /></div><div className="min-w-0"><DialogTitle>{t("users:bulkActions.assignPolicyDialogTitle", { count: userEmails.length })}</DialogTitle><button type="button" className="max-w-full truncate text-left text-sm text-fg-muted hover:text-brand-fg" onClick={() => setSelectedUsersOpen(true)}>{userEmails.length === 1 ? userEmails[0] : `${userEmails.length} users selected`}</button></div></div></DialogHeader>
          <div className={cn("min-h-0 flex flex-1 flex-col py-3 [scrollbar-gutter:stable]", tab === "permissions" ? "overflow-hidden" : "overflow-y-auto")}><div className={cn("rounded-lg border border-border-card bg-bg-surface p-3 shadow-card", (tab === "permissions" || tab === "policies") && "border-0 bg-transparent p-0 shadow-none flex min-h-0 flex-1 flex-col")}>
            {tab === "policies" && <BulkPolicyTab policies={availablePolicies} selectedPolicies={selectedPolicies} policySearch={policySearch} isAssigning={assignPolicy.isPending} isRemoving={removePolicy.isPending} onSearchChange={setPolicySearch} onToggle={(name, checked) => setSelectedPolicies((current) => checked ? [...current, name] : current.filter((value) => value !== name))} onRun={runPolicy} />}
            {tab === "permissions" && <BulkPermissionTab groups={permissionGroups} expandedGroups={expandedPermissionGroups} selectedPermissions={permissions} conditions={conditions} error={error} isGranting={grantPermission.isPending} isRevoking={revokePermission.isPending} onExpandedGroupsChange={setExpandedPermissionGroups} onPermissionChange={(key, checked) => setPermissions((current) => checked ? [...current, key] : current.filter((value) => value !== key))} onConditionsChange={setConditions} onRun={runPermission} />}
            {tab === "roles" && <BulkRoleTab role={role} isPending={updateRole.isPending} onRoleChange={setRole} onRun={runRole} />}
          </div></div>
        </div>
        <DialogFooter className={DIALOG_FOOTER_CLASSNAME}><Button onClick={onClose} variant="secondary">{t("ui_text:close")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
    <Dialog open={selectedUsersOpen} onOpenChange={setSelectedUsersOpen}><DialogContent closeLabel={t("ui_text:closeDialog")} className={cn("w-[calc(100vw-1.5rem)] sm:max-w-lg", DIALOG_PANEL_CLASSNAME)}><DialogHeader className={DIALOG_HEADER_CLASSNAME}><DialogTitle>{userEmails.length} users selected</DialogTitle></DialogHeader><div className="min-h-0 flex flex-col px-5 py-3 sm:px-6"><SearchInput value={selectedUserSearch} onChange={(value) => { setSelectedUserSearch(value); setSelectedUserPage(1); }} placeholder="Search selected users" resultsLabel={() => ""} loadingLabel="Loading" className="mb-3 w-full" /><div className="max-h-[min(24rem,calc(100svh-16rem))] overflow-y-auto rounded-lg border border-border-default bg-bg-surface p-2 [scrollbar-gutter:stable]">{visibleSelectedUsers.map((email) => <p key={email} className="truncate px-2 py-1.5 text-sm" title={email}>{email}</p>)}{!visibleSelectedUsers.length && <p className="px-2 py-8 text-center text-sm text-fg-muted">No selected users match your search.</p>}</div>{selectedUserPages > 1 && <div className="mt-3 flex items-center justify-between gap-2 text-sm text-fg-muted"><span>{filteredSelectedUsers.length} matching users</span><div className="flex items-center gap-2"><Button size="sm" variant="secondary" disabled={selectedUserPage <= 1} onClick={() => setSelectedUserPage((page) => page - 1)}>Previous</Button><span>{selectedUserPage} / {selectedUserPages}</span><Button size="sm" variant="secondary" disabled={selectedUserPage >= selectedUserPages} onClick={() => setSelectedUserPage((page) => page + 1)}>Next</Button></div></div>}</div><DialogFooter className={DIALOG_FOOTER_CLASSNAME}><Button variant="secondary" onClick={() => setSelectedUsersOpen(false)}>{t("ui_text:close")}</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={resultOpen && !!result} onOpenChange={setResultOpen}><DialogContent closeLabel={t("ui_text:closeDialog")} className={cn("w-[calc(100vw-1.5rem)] sm:max-w-2xl max-h-[min(44rem,calc(100svh-1.5rem))] flex flex-col overflow-hidden", DIALOG_PANEL_CLASSNAME)}><DialogHeader className={DIALOG_HEADER_CLASSNAME}><DialogTitle>{result ? t("users:bulkActions.resultSummary", { success: result.success_count, error: result.error_count }) : ""}</DialogTitle><p className="truncate text-sm text-fg-muted" title={resultOperationLabel}>{resultOperationLabel}</p></DialogHeader><div className="min-h-0 flex-1 overflow-y-auto px-5 py-3 sm:px-6 [scrollbar-gutter:stable]"><BulkOperationResultList results={result?.results ?? []} /></div><DialogFooter className={DIALOG_FOOTER_CLASSNAME}><Button variant="secondary" onClick={() => setResultOpen(false)}>{t("ui_text:close")}</Button></DialogFooter></DialogContent></Dialog>
  </>;
};

export default BulkUserAccessDialog;
