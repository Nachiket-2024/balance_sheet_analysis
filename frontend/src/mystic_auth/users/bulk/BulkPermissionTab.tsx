import React from "react";
import { ChevronRight, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "../../ui/buttons/Button";
import AppTooltip from "../../ui/feedback/AppTooltip";
import Badge from "../../ui/badges/Badge";
import { Textarea } from "../../ui/inputs/Textarea";
import { Switch } from "../../ui/shadcn/switch";
import FormAlert from "../../ui/feedback/FormAlert";
import { IfCan } from "../../authorization/IfCan";
import { PERMISSIONS } from "../../authorization/permissions";
import { isDestructiveAction } from "../../authorization/destructiveActions";
import {
  formatPolicyActionLabel,
  formatResourceTypeLabel,
  RESOURCE_TYPE_ICONS,
  resourceTypeIconTone,
} from "../../policies/policyCardHelpers";
import { toaster } from "../../ui/toaster/toasterInstance";
import { cn } from "../../ui/styles/classNames";

type PermissionEntry = {
  action: string;
  resource_type: string;
  description: string;
};

interface BulkPermissionTabProps {
  groups: Record<string, PermissionEntry[]>;
  expandedGroups: string[];
  selectedPermissions: string[];
  conditions: string;
  error: string | null;
  isGranting: boolean;
  isRevoking: boolean;
  onExpandedGroupsChange: (groups: string[]) => void;
  onPermissionChange: (key: string, checked: boolean) => void;
  onConditionsChange: (value: string) => void;
  onRun: (remove: boolean) => void;
}

const BulkPermissionTab: React.FC<BulkPermissionTabProps> = ({
  groups,
  expandedGroups,
  selectedPermissions,
  conditions,
  error,
  isGranting,
  isRevoking,
  onExpandedGroupsChange,
  onPermissionChange,
  onConditionsChange,
  onRun,
}) => {
  const { t } = useTranslation(["users", "ui_text"]);
  const names = Object.keys(groups);
  const allExpanded =
    names.length > 0 && names.every((name) => expandedGroups.includes(name));
  const toggleGroup = (name: string) =>
    onExpandedGroupsChange(
      expandedGroups.includes(name)
        ? expandedGroups.filter((value) => value !== name)
        : [...expandedGroups, name],
    );
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center justify-end gap-2 mb-2">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onExpandedGroupsChange(names)}
          disabled={allExpanded}
        >
          {t("ui_text:expandCollapseAll.expandAll")}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onExpandedGroupsChange([])}
          disabled={!expandedGroups.length}
        >
          {t("ui_text:expandCollapseAll.collapseAll")}
        </Button>
      </div>
      <div
        className="flex-1 min-h-0 overflow-y-auto pb-3 [scrollbar-gutter:stable]"
        role="group"
        aria-label={t("users:permissionsDialog.actionAriaLabel")}
      >
        <div className="flex flex-col gap-3">
          {Object.entries(groups).map(([resourceType, entries]) => {
            const expanded = expandedGroups.includes(resourceType);
            return (
              <section key={resourceType}>
                <button
                  type="button"
                  className={`sticky top-0 z-30 isolate flex w-full items-center gap-3 min-h-11 px-3 py-2.5 border border-border-default rounded-t-lg bg-bg-table-header text-fg-muted text-left focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-[-2px] ${expanded ? "rounded-b-none border-b" : "rounded-b-lg border-b"}`}
                  aria-expanded={expanded}
                  aria-label={`${expanded ? t("ui_text:expandCollapseAll.collapseAll") : t("ui_text:expandCollapseAll.expandAll")}: ${formatResourceTypeLabel(resourceType)}`}
                  onClick={() => toggleGroup(resourceType)}
                >
                  {(() => {
                    const ResourceIcon =
                      RESOURCE_TYPE_ICONS[resourceType] ??
                      RESOURCE_TYPE_ICONS["*"];
                    return (
                      <span className="flex min-w-0 flex-1 items-center gap-2">
                        <ChevronRight
                          size={16}
                          aria-hidden="true"
                          style={{
                            transform: expanded ? "rotate(90deg)" : undefined,
                            transition: "transform .15s",
                            flexShrink: 0,
                          }}
                        />
                        <ResourceIcon
                          size={18}
                          className={cn(
                            "shrink-0",
                            resourceTypeIconTone(resourceType),
                          )}
                          aria-hidden="true"
                        />
                        <span className="truncate text-sm leading-5 font-medium text-fg-default">
                          {formatResourceTypeLabel(resourceType)}
                        </span>
                      </span>
                    );
                  })()}
                  <span className="text-sm leading-5 text-fg-muted">
                    {t("users:accessDialog.actionCount", {
                      count: entries.length,
                    })}
                  </span>
                </button>
                {expanded && (
                  <div className="rounded-b-lg border-x border-b border-border-default bg-bg-surface p-2">
                    <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                      {entries.map((entry) => {
                        const key = `${entry.action}::${entry.resource_type}`;
                        const actionKey = `${entry.action}:${entry.resource_type}`;
                        const toggle = () =>
                          onPermissionChange(
                            key,
                            !selectedPermissions.includes(key),
                          );
                        return (
                          <div
                            key={key}
                            className="flex min-w-0 cursor-pointer items-center justify-between gap-3 rounded-lg border border-border-default bg-bg-surface px-3 py-2.5"
                            onClick={(event) => {
                              if (
                                (event.target as HTMLElement).closest(
                                  "button,[role='switch'],[data-slot='switch']",
                                )
                              )
                                return;
                              toggle();
                            }}
                          >
                            <span className="flex min-w-0 flex-1 flex-col py-0.5">
                              <span className="flex min-w-0 items-center gap-2">
                                <span
                                  className="min-w-0 flex-1 line-clamp-2 text-sm leading-5 font-medium text-fg-default"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    toggle();
                                  }}
                                >
                                  {entry.description ||
                                    formatPolicyActionLabel(entry.action)}
                                </span>
                                {isDestructiveAction(entry.action) && (
                                  <Badge
                                    size="xs"
                                    colorPalette="red"
                                    variant="subtle"
                                    className="shrink-0 whitespace-nowrap"
                                  >
                                    {t("users:accessDialog.sensitive")}
                                  </Badge>
                                )}
                              </span>
                            </span>
                            <div className="flex shrink-0 items-center gap-1">
                              <AppTooltip
                                content={t("users:accessDialog.copyKey", {
                                  key: actionKey,
                                })}
                              >
                                <Button
                                  type="button"
                                  size="2xs"
                                  variant="ghost"
                                  className="p-0.5 min-w-0 h-auto text-fg-muted shrink-0 opacity-60 hover:opacity-100 focus-visible:opacity-100"
                                  aria-label={t(
                                    "users:accessDialog.copyKey",
                                    { key: actionKey },
                                  )}
                                  onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    navigator.clipboard
                                      ?.writeText(actionKey)
                                      .catch(() => {});
                                    toaster.create({
                                      title: t(
                                        "users:accessDialog.copyKeyToast",
                                        { key: actionKey },
                                      ),
                                      type: "info",
                                    });
                                  }}
                                >
                                  <Copy size={12} aria-hidden="true" />
                                </Button>
                              </AppTooltip>
                              <Switch
                                checked={selectedPermissions.includes(key)}
                                onCheckedChange={(checked) =>
                                  onPermissionChange(key, !!checked)
                                }
                                aria-label={
                                  entry.description ||
                                  formatPolicyActionLabel(entry.action)
                                }
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </section>
            );
          })}
        </div>
      </div>
      <details
        className="rounded-lg border border-border-default bg-bg-canvas/30 px-3 py-2"
        open={Boolean(conditions)}
      >
        <summary className="cursor-pointer text-sm font-medium text-fg-default">
          {t("users:accessDialog.addConditions")}
        </summary>
        <p className="mt-1 text-xs text-fg-muted">
          {t("users:permissionsDialog.conditionsPlaceholder")}
        </p>
        <Textarea
          className="mt-2"
          rows={2}
          value={conditions}
          onChange={(event) => onConditionsChange(event.target.value)}
          placeholder={t("users:permissionsDialog.conditionsPlaceholder")}
        />
      </details>
      {error && <FormAlert status="error">{error}</FormAlert>}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="brand"
          onClick={() => onRun(false)}
          disabled={!selectedPermissions.length}
          loading={isGranting}
        >
          {t("users:bulkActions.grantToSelected")}
        </Button>
        <IfCan action={PERMISSIONS.PERMISSIONS_REVOKE}>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onRun(true)}
            disabled={!selectedPermissions.length}
            loading={isRevoking}
          >
            {t("users:bulkActions.revokeFromSelected")}
          </Button>
        </IfCan>
      </div>
    </div>
  );
};

export default BulkPermissionTab;
