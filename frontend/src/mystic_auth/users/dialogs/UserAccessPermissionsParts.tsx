import React, { useState } from "react";
import { ChevronRight, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import AppTooltip from "../../ui/feedback/AppTooltip";
import Badge from "../../ui/badges/Badge";
import FormAlert from "../../ui/feedback/FormAlert";
import { Button } from "../../ui/buttons/Button";
import { Textarea } from "../../ui/inputs/Textarea";
import { Switch } from "../../ui/shadcn/switch";
import { cn } from "../../ui/styles/classNames";
import { IfCan } from "../../authorization/IfCan";
import { useAuthorization } from "../../authorization/useAuthorization";
import { isDestructiveAction } from "../../authorization/destructiveActions";
import { PERMISSIONS } from "../../authorization/permissions";
import {
  formatPolicyActionLabel,
  formatResourceTypeLabel,
  RESOURCE_TYPE_ICONS,
  resourceTypeIconTone,
} from "../../policies/policyCardHelpers";
import { CopyKeyButton, type CatalogEntry, type UserAccessState } from "./UserAccessDialogAtoms";

// Permissions tab of the User Access dialog: the per-action switch, the
// grouped table it sits in, its conditions editor, and the resource-type
// group header. Policies-tab rendering (PolicyActionsTable) lives in
// UserAccessDialogParts.tsx, shared atoms in UserAccessDialogAtoms.tsx -
// split out of one 576-line file, see AGENTS.md's ~350-line target.

function PermissionEntrySwitch({
  entry,
  state,
  locked,
  lockText,
}: {
  entry: CatalogEntry;
  state: UserAccessState;
  locked: boolean;
  lockText?: string;
}) {
  const { t } = useTranslation(["users", "ui_text"]);
  const { can } = useAuthorization();
  const direct = state.directGrants.some(
    (grant) =>
      grant.action === entry.action &&
      grant.resource_type === entry.resource_type,
  );
  const viaPolicy =
    !direct &&
    state.isAlreadyEffectivelyGranted(
      state.effectiveGrantKeys,
      entry.action,
      entry.resource_type,
    );
  // The API deliberately prevents privilege escalation: a caller must already
  // hold a built-in action before granting or removing that action. Reflect
  // that rule here instead of allowing a click that can only end in 403.
  const callerCannotManageAction = !can(entry.action);
  const label = locked
    ? lockText
    : viaPolicy
      ? t("users:accessDialog.comesFromPolicy")
      : callerCannotManageAction
        ? t("users:accessDialog.cannotGrantUnheld")
        : direct
          ? t("users:accessDialog.removeDirect")
          : t("users:accessDialog.giveDirect");
  return (
    <IfCan
      action={
        direct ? PERMISSIONS.PERMISSIONS_REVOKE : PERMISSIONS.PERMISSIONS_GRANT
      }
    >
      <AppTooltip content={label}>
        <Switch
          checked={direct || viaPolicy}
          disabled={locked || viaPolicy || callerCannotManageAction}
          onCheckedChange={() =>
            state.toggleDirectPermission(entry.action, entry.resource_type)
          }
          aria-label={label}
          className={cn(
            viaPolicy && !locked && "disabled:opacity-100",
          )}
        />
      </AppTooltip>
    </IfCan>
  );
}

function ConditionsEditor({
  entry,
  state,
}: {
  entry: CatalogEntry;
  state: UserAccessState;
}) {
  const { t } = useTranslation(["users", "ui_text"]);
  const direct = state.directGrants.find(
    (grant) =>
      grant.action === entry.action &&
      grant.resource_type === entry.resource_type,
  );
  const [text, setText] = useState(
    direct?.conditions ? JSON.stringify(direct.conditions) : "",
  );
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-2 bg-bg-card-head rounded-md p-3 border border-border-card">
      <p className="text-sm text-fg-muted">
        {t("users:permissionsDialog.conditionsPlaceholder")}
      </p>
      <Textarea
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="text-sm"
      />
      {error && <FormAlert status="error">{error}</FormAlert>}
      <div className="flex items-center gap-2">
        <Button
          size="xs"
          variant="brand"
          onClick={() =>
            setError(
              state.saveConditions(entry.action, entry.resource_type, text),
            )
          }
          loading={state.grantMutation.isPending}
        >
          {t("ui_text:save")}
        </Button>
        <Button
          size="xs"
          variant="ghost"
          onClick={() => state.setEditingKey(null)}
        >
          {t("ui_text:cancel")}
        </Button>
      </div>
    </div>
  );
}

function PermissionItemsTable({
  items,
  state,
  locked,
  lockText,
}: {
  items: CatalogEntry[];
  state: UserAccessState;
  locked: boolean;
  lockText?: string;
}) {
  const { t } = useTranslation(["users", "ui_text"]);
  const { can } = useAuthorization();
  const editing = items.find(
    (entry) =>
      state.editingKey === state.armKey(entry.action, entry.resource_type),
  );
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        {items.map((entry) => {
          const direct = state.directGrants.some(
            (grant) =>
              grant.action === entry.action &&
              grant.resource_type === entry.resource_type,
          );
          const viaPolicy =
            !direct &&
            state.isAlreadyEffectivelyGranted(
              state.effectiveGrantKeys,
              entry.action,
              entry.resource_type,
            );
          const canToggle =
            !locked &&
            !viaPolicy &&
            can(entry.action) &&
            can(
              direct
                ? PERMISSIONS.PERMISSIONS_REVOKE
                : PERMISSIONS.PERMISSIONS_GRANT,
            );
          const toggleFromContent = (event?: React.MouseEvent) => {
            event?.stopPropagation();
            if (canToggle)
              state.toggleDirectPermission(entry.action, entry.resource_type);
          };
          return (
            <div
              key={`${entry.action}:${entry.resource_type}`}
              className={cn(
                "flex min-w-0 items-center justify-between gap-3 rounded-lg border border-border-default bg-bg-surface px-3 py-2.5",
                canToggle && "cursor-pointer",
              )}
              onClick={(event) => {
                if (
                  !canToggle ||
                  (event.target as HTMLElement).closest(
                    "button,[role='switch'],[data-slot='switch']",
                  )
                )
                  return;
                toggleFromContent();
              }}
            >
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-start gap-2">
                  <p
                    className={cn(
                      "min-w-0 flex-1 line-clamp-2 text-sm font-medium",
                      canToggle && "cursor-pointer",
                    )}
                    onClick={toggleFromContent}
                  >
                    {entry.description || formatPolicyActionLabel(entry.action)}
                  </p>
                  {isDestructiveAction(entry.action) && (
                    <Badge
                      size="xs"
                      colorPalette="red"
                      variant="subtle"
                      className="shrink-0 leading-none"
                    >
                      {t("users:accessDialog.sensitive")}
                    </Badge>
                  )}
                </div>
                <div className="text-[13px] text-fg-muted">
                  {direct
                    ? t("users:accessDialog.givenDirectly")
                    : viaPolicy
                      ? t("users:accessDialog.fromPolicyShort")
                      : ""}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <CopyKeyButton
                  actionKey={`${entry.action}:${entry.resource_type}`}
                />
                <PermissionEntrySwitch
                  entry={entry}
                  state={state}
                  locked={locked}
                  lockText={lockText}
                />
              </div>
            </div>
          );
        })}
      </div>
      {editing && <ConditionsEditor entry={editing} state={state} />}
    </div>
  );
}

export function PermissionGroup({
  group,
  items,
  state,
  locked,
  lockText,
}: {
  group: string;
  items: CatalogEntry[];
  state: UserAccessState;
  locked: boolean;
  lockText?: string;
}) {
  const { t } = useTranslation("users");
  const open = !state.permClosedGroups.has(group) || !!state.permQuery;
  const granted = items.filter((entry) =>
    state.isAlreadyEffectivelyGranted(
      state.effectiveGrantKeys,
      entry.action,
      entry.resource_type,
    ),
  ).length;
  const ResourceIcon = RESOURCE_TYPE_ICONS[group] ?? ShieldCheck;
  return (
    <div>
      <button
        type="button"
        className="sticky top-0 z-30 flex w-full items-center gap-3 min-h-11 px-3 py-2.5 border border-border-default rounded-t-lg bg-bg-table-header text-left focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-2"
        aria-expanded={open}
        aria-label={`${open ? t("accessDialog.collapseGroup") : t("accessDialog.expandGroup")}: ${formatResourceTypeLabel(group)}`}
        onClick={() => state.togglePermGroup(group)}
      >
        <span className="flex min-w-0 flex-1 items-center gap-2">
          <ChevronRight
            size={16}
            aria-hidden="true"
            style={{ transform: open ? "rotate(90deg)" : undefined }}
          />
          <ResourceIcon
            size={18}
            className={cn("shrink-0", resourceTypeIconTone(group))}
            aria-hidden="true"
          />
          <span className="text-sm leading-5 font-medium">
            {formatResourceTypeLabel(group)}
          </span>
        </span>
        <span className="text-sm leading-5 text-fg-muted">
          {granted
            ? t("accessDialog.groupAllowedCount", {
                granted,
                total: items.length,
              })
            : t("accessDialog.actionCount", { count: items.length })}
        </span>
      </button>
      {open && (
        <div className="rounded-b-lg border-x border-b border-border-default bg-bg-surface p-2">
          <PermissionItemsTable
            items={items}
            state={state}
            locked={locked}
            lockText={lockText}
          />
        </div>
      )}
    </div>
  );
}
