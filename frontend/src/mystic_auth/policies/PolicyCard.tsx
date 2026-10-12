import React from "react";
import {
  ChevronRight,
  Eye,
  Lock,
  Pencil,
  ShieldCheck,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import Badge from "../ui/badges/Badge";
import AppTooltip from "../ui/feedback/AppTooltip";
import TableActionIconButton from "../ui/table_actions/TableActionIconButton";
import { Switch } from "../ui/shadcn/switch";
import { cn } from "../ui/styles/classNames";
import { IfCan } from "../authorization/IfCan";
import { useAuthorization } from "../authorization/useAuthorization";
import { canGrantPolicy } from "../authorization/grantability";
import { isDestructiveAction } from "../authorization/destructiveActions";
import { PERMISSIONS } from "../authorization/permissions";
import {
  formatResourceTypeLabel,
  PROTECTED_POLICY_NAMES,
  RESOURCE_TYPE_ICONS,
  resourceTypeIconTone,
} from "./policyCardHelpers";
import PolicyActionGroups from "./PolicyActionGroups";
import type { PolicyRead } from "../api/policies_api";

// A fixed status green, not brand: design/policies.html's
// .switch[aria-checked="true"] is a fixed status green, not the
// user-customizable brand color - this is a status/state (design.md: status
// colors stay separate from brand), not a brand accent. shadcn's Switch
// defaults data-[state=checked] to bg-primary (the brand color), so this
// overrides it to the app's green-500/green-600 steps already ported to
// tailwind.css (see audit_log's LoginTrendChart green.500 addition).
const GREEN_SWITCH_CLASSNAME =
  "data-[state=checked]:bg-[var(--green-500)] dark:data-[state=checked]:bg-[var(--green-600)]";

interface PolicyCardProps {
  policy: PolicyRead;
  isOpen: boolean;
  onToggleOpen: (policyName: string) => void;
  onView: (policy: PolicyRead, trigger: HTMLElement) => void;
  onEdit: (policy: PolicyRead) => void;
  onToggleActive: (policy: PolicyRead) => void;
  isTogglingActive: boolean;
  onDeleteRequest: (policy: PolicyRead) => void;
  highlight?: string;
}

/** One policy's row + expandable action list, replacing the old DataTable
 * row (design/policies.html: "cards instead of a table, with a gap between
 * them"). Same interaction split as PermissionsPage's resource-type group
 * header: clicking anywhere on the row (other than a button) toggles the
 * expanded action list, and a separate, explicit View button opens the
 * read-only details dialog - clicking the row itself used to open that
 * dialog, which collided with wanting the row to also expand/collapse. The
 * chevron is a plain icon, not its own boxed button, since the whole row
 * already carries its click behavior. */
const PolicyCard: React.FC<PolicyCardProps> = ({
  policy,
  isOpen,
  onToggleOpen,
  onView,
  onEdit,
  onToggleActive,
  isTogglingActive,
  onDeleteRequest,
}) => {
  const { t } = useTranslation(["policies", "ui_text"]);
  const { can } = useAuthorization();
  const isProtected = PROTECTED_POLICY_NAMES.has(policy.name);
  const isSystemSuperuser = policy.name === "system_superuser";
  const destructiveCount = policy.actions.filter(isDestructiveAction).length;
  const ResourceIcon = RESOURCE_TYPE_ICONS[policy.resource_type] ?? ShieldCheck;
  // The backend requires the caller to already hold every action affected by
  // status changes and deletion. Keep those controls visible when the caller
  // has the management permission, but make the stronger grant guard clear.
  const canManageCurrentGrant = canGrantPolicy(policy, can);
  const grantGuardMessage = t("policies:columns.cannotManageGrantWithoutActions");

  const toggleOpen = () => onToggleOpen(policy.name);

  return (
    <div>
      {/* The whole header row expands/collapses. The explicit control keeps
          the same interaction keyboard-operable and announces its state. */}
      <div
        className={cn(
          "flex cursor-pointer items-center gap-3 rounded-[12px] border border-border-default bg-bg-surface p-3 text-left shadow-card transition-[background-color,border-color] duration-[var(--duration-fast)] ease-[var(--easing-hover)] hover:border-[var(--brand-500)] hover:bg-brand-tile-subtle",
          isOpen ? "rounded-b-none border-b-0" : "rounded-b-lg",
        )}
        onClick={toggleOpen}
      >
        <button
          type="button"
          className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 text-left focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-2"
          onClick={(event) => {
            event.stopPropagation();
            toggleOpen();
          }}
          aria-expanded={isOpen}
          aria-controls={`policy-actions-${policy.id}`}
          aria-label={t(isOpen ? "policies:columns.collapsePolicy" : "policies:columns.expandPolicy", { name: policy.name })}
        >
          <span className="shrink-0">
            <ChevronRight
              size={16}
              aria-hidden="true"
              style={{
                transform: isOpen ? "rotate(90deg)" : undefined,
                transition: "transform var(--duration-hover)",
              }}
            />
          </span>

          {/* Plain inline icon, no tinted box: the resource-type pill next
                    to the name already states this in words, so a brand-colored
                    box here would just repeat it on every row. */}
          <ResourceIcon
            size={18}
            className={cn(
              "shrink-0",
              resourceTypeIconTone(policy.resource_type),
            )}
            aria-hidden="true"
          />

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-medium truncate">{policy.name}</p>
              {/* Neutral pill (design/policies.html's .tag), not a
                            brand-colored badge: design.md's exception for
                            "small elements repeated on every row" - a
                            brand-tinted chip on every single card would
                            compete with the avatar box, the one element on
                            this row that should actually carry the brand
                            tint. */}
              <Badge colorPalette="gray" variant="outline" size="sm">
                {formatResourceTypeLabel(policy.resource_type)}
              </Badge>
              {!policy.is_active && (
                <Badge colorPalette="gray" size="sm">
                  {t("policies:columns.inactive")}
                </Badge>
              )}
              {isProtected && (
                <Badge colorPalette="gray" variant="subtle" size="sm">
                  <Lock size={11} aria-hidden="true" />
                  {t("policies:columns.protected")}
                </Badge>
              )}
              <span className="text-xs font-medium text-fg-muted">
                {t("policies:columns.actionCount", { count: policy.actions.length })}
              </span>
              <span className="text-xs text-fg-muted">
                {t("policies:columns.holderCount", { count: policy.holder_count ?? 0 })}
              </span>
              {destructiveCount > 0 && (
                <span className="flex items-center gap-1 text-xs font-medium text-red-fg" title={t("policies:columns.destructiveCount", { count: destructiveCount })}>
                  <TriangleAlert size={13} aria-hidden="true" />
                  {t("policies:columns.destructiveCount", { count: destructiveCount })}
                </span>
              )}
            </div>
            <div className="mt-0.5 min-w-0 text-sm text-fg-muted">
              {policy.description && (
                <p className="line-clamp-2 leading-5">
                  {policy.description}
                </p>
              )}
            </div>
          </div>
        </button>

        <div
          className="flex items-center gap-1.5 shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          <TableActionIconButton
            colorPalette="neutral"
            label={t("policies:columns.view")}
            data-policy-name={policy.name}
            onClick={(event) => onView(policy, event.currentTarget)}
          >
            <Eye size={18} aria-hidden="true" />
          </TableActionIconButton>
          <IfCan action={PERMISSIONS.POLICIES_UPDATE}>
            <TableActionIconButton
              colorPalette="neutral"
              label={t("policies:columns.edit")}
              disabled={isProtected}
              disabledLabel={t("policies:columns.cannotEditProtectedPolicy")}
              onClick={() => onEdit(policy)}
            >
              <Pencil size={18} aria-hidden="true" />
            </TableActionIconButton>
          </IfCan>
          {/* Right next to Delete, not up by View/Edit: both are the
                        row's state-changing actions on the policy itself
                        (one reversible, one not), grouped together the same
                        way Users groups Deactivate/Reactivate next to
                        Delete. */}
          <IfCan action={PERMISSIONS.POLICIES_UPDATE}>
            <AppTooltip
              content={
                isSystemSuperuser
                  ? t("policies:columns.systemSuperuserAlwaysActive")
                  : isProtected
                    ? t("policies:columns.cannotModifyBaselinePolicy")
                    : !canManageCurrentGrant
                      ? grantGuardMessage
                    : policy.is_active
                      ? t("policies:columns.deactivate")
                      : t("policies:columns.activate")
              }
            >
              <div>
                {/* Every PROTECTED_POLICY_NAMES entry, not just
                                    system_superuser: the backend rejects
                                    deactivating self_service/user_management
                                    too (same PROTECTED_POLICY_NAMES the Delete
                                    button below is already gated on) - this used
                                    to only special-case system_superuser, so the
                                    other two baseline policies' switches looked
                                    enabled right up until the PUT came back 403. */}
                <Switch
                  checked={policy.is_active}
                  disabled={isProtected || !canManageCurrentGrant || isTogglingActive}
                  onCheckedChange={() => onToggleActive(policy)}
                  className={GREEN_SWITCH_CLASSNAME}
                  aria-label={
                    policy.is_active
                      ? t("policies:columns.deactivate")
                      : t("policies:columns.activate")
                  }
                />
              </div>
            </AppTooltip>
          </IfCan>
          {!policy.is_active && (
            <IfCan action={PERMISSIONS.POLICIES_DELETE}>
              <TableActionIconButton
                colorPalette="red"
                label={t("ui_text:delete")}
                disabled={isProtected || !canManageCurrentGrant}
                disabledLabel={isProtected ? t("policies:columns.cannotDeleteProtectedPolicy") : grantGuardMessage}
                onClick={() => onDeleteRequest(policy)}
              >
                <Trash2 size={18} aria-hidden="true" />
              </TableActionIconButton>
            </IfCan>
          )}
        </div>
      </div>

      {isOpen && (
        // Same bordered/rounded-b-lg body shape as PermissionsPage's
        // expanded DataTable wrapper, sat directly under the header
        // (which drops its own bottom border/radius above) - still a
        // distinct sunken tray (bg-bg-canvas, not the header's
        // bg-bg-surface) so it visibly reads as "this expanded out of
        // the header above." PolicyActionGroups lays the verb groups
        // out in CSS multi-column flow (not a linear top-to-bottom
        // list) - see its own docstring.
        <div id={`policy-actions-${policy.id}`} className="px-4 pb-4 pt-3 bg-bg-canvas border border-border-default rounded-b-lg">
          <PolicyActionGroups actions={policy.actions} />
        </div>
      )}
    </div>
  );
};

export default PolicyCard;
