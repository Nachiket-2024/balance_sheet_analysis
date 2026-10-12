import React from "react";
import { useTranslation } from "react-i18next";

import AppTooltip from "../../ui/feedback/AppTooltip";
import Badge from "../../ui/badges/Badge";
import { Switch } from "../../ui/shadcn/switch";
import { cn } from "../../ui/styles/classNames";
import { IfCan } from "../../authorization/IfCan";
import { isDestructiveAction } from "../../authorization/destructiveActions";
import { PERMISSIONS } from "../../authorization/permissions";
import { formatPolicyActionLabel } from "../../policies/policyCardHelpers";
import { CopyKeyButton, type CatalogEntry, type UserAccessState } from "./UserAccessDialogAtoms";

// Policies tab of the User Access dialog: the per-action table shown when a
// policy is expanded. Shared atoms (types, FilterSegment/StatTile/InfoRow,
// accessChangeLabel) live in UserAccessDialogAtoms.tsx, the Permissions
// tab's own parts in UserAccessPermissionsParts.tsx - split out of one
// 576-line file, see AGENTS.md's ~350-line target.

export function PolicyActionsTable({
  policy,
  assigned,
  locked,
  selfProtected,
  lockText,
  catalog,
  state,
}: {
  policy: { name: string; resource_type: string; actions: string[] };
  assigned: boolean;
  locked: boolean;
  selfProtected: boolean;
  lockText?: string;
  catalog: CatalogEntry[];
  state: UserAccessState;
}) {
  const { t } = useTranslation(["users", "ui_text"]);
  return (
    <div className="grid grid-cols-1 gap-2 p-2 sm:grid-cols-2">
      {policy.actions.map((action) => {
        const entry = catalog.find(
          (item) =>
            item.action === action &&
            item.resource_type === policy.resource_type,
        );
        const label = entry?.description || formatPolicyActionLabel(action);
        const canToggle = assigned && !locked && !selfProtected;
        const toggleFromContent = (event?: React.MouseEvent) => {
          event?.stopPropagation();
          if (canToggle) state.requestRevokePolicyAction(policy.name, action);
        };
        return (
          <div
            key={action}
            className={cn(
              "flex min-w-0 items-center justify-between gap-3 rounded-lg border border-border-default bg-bg-surface px-3 py-2.5",
              canToggle && "cursor-pointer",
            )}
            onClick={toggleFromContent}
          >
            <div className="flex min-w-0 flex-1 flex-wrap items-start gap-2">
              <p
                className={cn(
                  "min-w-0 flex-1 line-clamp-2 text-sm font-medium",
                  canToggle && "cursor-pointer",
                )}
                onClick={toggleFromContent}
              >
                {label}
              </p>
              {isDestructiveAction(action) && (
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
            <div className="flex shrink-0 items-center gap-1">
              <CopyKeyButton actionKey={`${action}:${policy.resource_type}`} />
              {assigned && (
                <IfCan action={PERMISSIONS.POLICIES_REVOKE}>
                  <AppTooltip
                    content={
                      locked
                        ? lockText
                        : selfProtected
                          ? t("users:accessDialog.selfProtectedPolicyLocked")
                          : t("users:policiesDialog.revokeActionTitle")
                    }
                  >
                    <Switch
                      checked
                      disabled={locked || selfProtected}
                      onCheckedChange={() =>
                        state.requestRevokePolicyAction(policy.name, action)
                      }
                      aria-label={t(
                        "users:policiesDialog.revokeActionAriaLabel",
                        {
                          action: formatPolicyActionLabel(action),
                          policyName: policy.name,
                        },
                      )}
                    />
                  </AppTooltip>
                </IfCan>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
