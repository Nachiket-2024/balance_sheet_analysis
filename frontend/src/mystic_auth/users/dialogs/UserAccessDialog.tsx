import React, { useRef } from "react";
import { Key, Shield, ShieldCheck, User as UserIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import GlossaryHelp from "../../ui/display/GlossaryHelp";
import Badge from "../../ui/badges/Badge";
import FormAlert from "../../ui/feedback/FormAlert";
import { Button } from "../../ui/buttons/Button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../ui/shadcn/dialog";
import { Tabs } from "../../ui/shadcn/tabs";
import { cn } from "../../ui/styles/classNames";
import { useLanguageStore } from "../../store/languageStore";
import { initialsFor } from "../../layout/app_layout/initialsFor";
import type { ManagedUserRead } from "../../api/users_api";
import { useUserAccessDialogState } from "./useUserAccessDialogState";
import UserAccessTabs from "./UserAccessTabs";
import {
  DIALOG_FOOTER_CLASSNAME,
  DIALOG_HEADER_CLASSNAME,
  DIALOG_PANEL_CLASSNAME,
} from "../../ui/styles/dialogStyles";

interface UserAccessDialogProps {
  isOpen: boolean;
  user: ManagedUserRead | null;
  initialTab?: "details" | "policies" | "permissions";
  isSystemUser?: boolean;
  onClose: () => void;
}

const UserAccessDialog: React.FC<UserAccessDialogProps> = ({
  isOpen,
  user,
  initialTab,
  isSystemUser = false,
  onClose,
}) => {
  const { t } = useTranslation(["users", "ui_text", "policies"]);
  const language = useLanguageStore((state) => state.chromeLanguage);
  const navigate = useNavigate();
  const state = useUserAccessDialogState(
    isOpen,
    user?.email ?? null,
    initialTab,
  );
  const tabValues: Array<"details" | "policies" | "permissions"> = [
    "details",
    "policies",
    "permissions",
  ];
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  if (!user) return null;
  const locked = isSystemUser;
  const lockText = isSystemUser
    ? t("users:columns.cannotModifySystemUser")
    : undefined;
  const catalog = state.catalogQuery.data ?? [];
  const totalGranted = catalog.filter((entry) =>
    state.isAlreadyEffectivelyGranted(
      state.effectiveGrantKeys,
      entry.action,
      entry.resource_type,
    ),
  ).length;
  const allPolicies = [
    ...new Map(
      [...state.assignedPolicies, ...(state.allPoliciesQuery.data ?? [])].map(
        (policy) => [policy.name, policy],
      ),
    ).values(),
  ];
  const policyQuery = state.polQuery.trim().toLowerCase();
  // Keep the catalog order stable while toggles refresh assignment state.
  // Sorting assigned policies to the top made the row jump immediately
  // after a click, forcing permission holders to relocate the item they just
  // changed. The filter still controls visibility; assignment should not.
  const policyRows = allPolicies
    .filter(
      (policy) =>
        state.polFilter === "all" ||
        (state.polFilter === "on") === state.assignedNames.has(policy.name),
    )
    .filter(
      (policy) =>
        !policyQuery ||
        policy.name.toLowerCase().includes(policyQuery) ||
        policy.description?.toLowerCase().includes(policyQuery),
    )
    .sort((a, b) => a.name.localeCompare(b.name));
  const permissionQuery = state.permQuery.trim().toLowerCase();
  const permissionRows = catalog.filter(
    (entry) =>
      (state.permFilter === "all" ||
        (state.permFilter === "on") ===
          state.isAlreadyEffectivelyGranted(
            state.effectiveGrantKeys,
            entry.action,
            entry.resource_type,
          )) &&
      (!permissionQuery ||
        entry.action.toLowerCase().includes(permissionQuery) ||
        entry.description?.toLowerCase().includes(permissionQuery) ||
        entry.resource_type.toLowerCase().includes(permissionQuery)),
  );
  const permissionGroups = [
    ...new Set(catalog.map((entry) => entry.resource_type)),
  ].filter((group) =>
    permissionRows.some((entry) => entry.resource_type === group),
  );
  const setTab = (tab: "details" | "policies" | "permissions") =>
    state.setTab(tab);
  const activateTab = (nextTab: "details" | "policies" | "permissions") => {
    setTab(nextTab);
    requestAnimationFrame(() =>
      tabRefs.current[tabValues.indexOf(nextTab)]?.focus(),
    );
  };
  const handleTabKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    currentTab: "details" | "policies" | "permissions",
  ) => {
    const currentIndex = tabValues.indexOf(currentTab);
    const nextIndex =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? (currentIndex + 1) % tabValues.length
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? (currentIndex + tabValues.length - 1) % tabValues.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? tabValues.length - 1
              : currentIndex;

    if (nextIndex !== currentIndex) {
      event.preventDefault();
      activateTab(tabValues[nextIndex]);
    }
  };

  return (
    <Dialog
      modal={false}
      open={isOpen}
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent
        overlayClassName="backdrop-blur-[2px]"
        closeLabel={t("ui_text:closeDialog")}
        className={cn(
          "w-[calc(100vw-1.5rem)] sm:max-w-3xl lg:max-w-[55rem] h-[min(44rem,calc(100svh-1.5rem))] flex flex-col overflow-hidden",
          DIALOG_PANEL_CLASSNAME,
        )}
      >
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-5 sm:px-6 bg-bg-canvas/60">
          <Tabs
            value={state.tab}
            onValueChange={(value) =>
              setTab(value as "details" | "policies" | "permissions")
            }
            className="flex min-h-0 flex-1 flex-col"
          >
            <div className="sticky top-0 z-30 flex items-center gap-2 bg-bg-canvas pb-2">
              <div
                role="tablist"
                aria-label={t("users:accessDialog.tabDetails")}
                className="flex min-w-0 flex-1 items-center gap-0 overflow-hidden rounded-lg border border-border-strong bg-bg-surface"
              >
                <button
                  ref={(element) => {
                    tabRefs.current[0] = element;
                  }}
                  type="button"
                  role="tab"
                  aria-selected={state.tab === "details"}
                  aria-controls="user-access-tabpanel-details"
                  tabIndex={state.tab === "details" ? 0 : -1}
                  onClick={() => activateTab("details")}
                  onKeyDown={(event) => handleTabKeyDown(event, "details")}
                  className={cn(
                    "inline-flex h-9 min-w-0 flex-1 cursor-pointer items-center justify-center gap-2 px-3 text-sm font-semibold transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-[-2px]",
                    state.tab === "details"
                      ? "bg-brand-tile-subtle text-brand-fg shadow-[inset_0_0_0_2px_var(--brand-solid)]"
                      : "text-fg-muted hover:bg-brand-subtle hover:text-brand-fg",
                  )}
                >
                  <UserIcon size={16} aria-hidden="true" />
                  {t("users:accessDialog.tabDetails")}
                </button>
                <button
                  ref={(element) => {
                    tabRefs.current[1] = element;
                  }}
                  type="button"
                  role="tab"
                  aria-selected={state.tab === "policies"}
                  aria-controls="user-access-tabpanel-policies"
                  tabIndex={state.tab === "policies" ? 0 : -1}
                  onClick={() => activateTab("policies")}
                  onKeyDown={(event) => handleTabKeyDown(event, "policies")}
                  className={cn(
                    "inline-flex h-9 min-w-0 flex-1 cursor-pointer items-center justify-center gap-2 border-l border-border-strong px-3 text-sm font-semibold transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-[-2px]",
                    state.tab === "policies"
                      ? "bg-brand-tile-subtle text-brand-fg shadow-[inset_0_0_0_2px_var(--brand-solid)]"
                      : "text-fg-muted hover:bg-brand-subtle hover:text-brand-fg",
                  )}
                >
                  <Shield size={16} aria-hidden="true" />
                  {t("users:accessDialog.tabPolicies")}
                  <span
                    className={cn(
                      "min-w-5 rounded-full px-1.5 text-center text-xs",
                      state.tab === "policies"
                        ? "bg-brand-solid text-white"
                        : "bg-bg-muted text-fg-muted",
                    )}
                  >
                    {state.assignedPolicies.length}
                  </span>
                </button>
                <button
                  ref={(element) => {
                    tabRefs.current[2] = element;
                  }}
                  type="button"
                  role="tab"
                  aria-selected={state.tab === "permissions"}
                  aria-controls="user-access-tabpanel-permissions"
                  tabIndex={state.tab === "permissions" ? 0 : -1}
                  onClick={() => activateTab("permissions")}
                  onKeyDown={(event) => handleTabKeyDown(event, "permissions")}
                  className={cn(
                    "inline-flex h-9 min-w-0 flex-1 cursor-pointer items-center justify-center gap-2 border-l border-border-strong px-3 text-sm font-semibold transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-[-2px]",
                    state.tab === "permissions"
                      ? "bg-brand-tile-subtle text-brand-fg shadow-[inset_0_0_0_2px_var(--brand-solid)]"
                      : "text-fg-muted hover:bg-brand-subtle hover:text-brand-fg",
                  )}
                >
                  <Key size={16} aria-hidden="true" />
                  {t("users:accessDialog.tabPermissions")}
                  <span
                    className={cn(
                      "min-w-5 rounded-full px-1.5 text-center text-xs",
                      state.tab === "permissions"
                        ? "bg-brand-solid text-white"
                        : "bg-bg-muted text-fg-muted",
                    )}
                  >
                    {totalGranted}
                  </span>
                </button>
              </div>
              <GlossaryHelp
                ariaLabel={t("users:accessDialog.glossaryAriaLabel")}
                items={[
                  {
                    term: t("users:accessDialog.glossary.policyTerm"),
                    definition: t(
                      "users:accessDialog.glossary.policyDefinition",
                    ),
                  },
                  {
                    term: t("users:accessDialog.glossary.permissionTerm"),
                    definition: t(
                      "users:accessDialog.glossary.permissionDefinition",
                    ),
                  },
                  {
                    term: t("users:accessDialog.glossary.roleTerm"),
                    definition: t("users:accessDialog.glossary.roleDefinition"),
                  },
                ]}
              />
            </div>
            <DialogHeader
              className={cn(
                DIALOG_HEADER_CLASSNAME,
                "sticky top-11 z-20 -mx-5 mt-1 bg-bg-canvas px-5 pr-0 sm:-mx-6 sm:px-6",
              )}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 shrink-0 rounded-full border border-[var(--brand-400)] bg-brand-subtle text-brand-fg flex items-center justify-center text-sm font-bold">
                  {initialsFor(user.name, user.email)}
                </div>
                <div className="flex flex-col min-w-0">
                  <div className="flex items-center gap-2 min-w-0">
                    <DialogTitle className="truncate">{user.name}</DialogTitle>
                    <Badge
                      colorPalette={user.role ? "brand" : "gray"}
                      variant="subtle"
                      className="px-2 py-0.5 text-xs font-bold rounded-full capitalize inline-flex items-center gap-1 shrink-0"
                    >
                      <ShieldCheck size={12} />
                      {user.role ?? t("users:detailsDialog.noRoleAssigned")}
                    </Badge>
                  </div>
                  <p className="text-sm text-fg-muted truncate">{user.email}</p>
                </div>
              </div>
            </DialogHeader>
            {locked && (
              <div className="mt-3">
                <FormAlert status="warning">{lockText}</FormAlert>
              </div>
            )}
            <UserAccessTabs
              user={user}
              state={state}
              language={language}
              locked={locked}
              lockText={lockText}
              totalGranted={totalGranted}
              allPolicies={allPolicies}
              policyRows={policyRows}
              permissionRows={permissionRows}
              permissionGroups={permissionGroups}
              catalog={catalog}
              t={t}
              navigate={navigate}
              onTabChange={setTab}
            />
          </Tabs>
        </div>
        <DialogFooter className={DIALOG_FOOTER_CLASSNAME}>
          <p className="text-sm text-fg-muted me-auto">
            {t("users:accessDialog.footerNote")}
          </p>
          <Button onClick={onClose} variant="secondary">
            {t("ui_text:close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default UserAccessDialog;
