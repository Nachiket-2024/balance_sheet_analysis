/* eslint-disable react-refresh/only-export-components -- mixes components with plain types/formatters shared across the dialog. */
import React from "react";
import { Copy } from "lucide-react";
import { useTranslation } from "react-i18next";

import AppTooltip from "../../ui/feedback/AppTooltip";
import { Button } from "../../ui/buttons/Button";
import { cn } from "../../ui/styles/classNames";
import QuickFilterSegment, {
  type QuickFilterOption,
} from "../../ui/filters/QuickFilterSegment";
import { DIALOG_DETAIL_LABEL_CLASSNAME } from "../../ui/styles/dialogStyles";
import type { SecurityAuditLogEntryRead } from "../../api/audit_api";
import type { useUserAccessDialogState } from "./useUserAccessDialogState";

// Small, shared pieces of the User Access dialog: types, filter/stat/info
// building blocks, and the access-change label formatter. Used by both
// UserAccessDialogParts.tsx (Policies tab) and UserAccessPermissionsParts.tsx
// (Permissions tab) - split out on its own so neither of those two has to
// import from the other, see AGENTS.md's ~350-line file-size target.

export type UserAccessState = ReturnType<typeof useUserAccessDialogState>;
export type Translate = (key: string, options?: Record<string, unknown>) => string;
export type CatalogEntry = {
  action: string;
  resource_type: string;
  description: string;
};

export const FilterSegment: React.FC<{
  value: "all" | "on" | "off";
  onChange: (value: "all" | "on" | "off") => void;
  counts: Record<"all" | "on" | "off", number>;
  labels: Record<"all" | "on" | "off", string>;
}> = ({ value, onChange, counts, labels }) => {
  const options: QuickFilterOption[] = (["all", "on", "off"] as const).map(
    (filter) => ({
      value: filter,
      label: labels[filter],
      count: counts[filter],
    }),
  );
  return (
    <QuickFilterSegment
      value={value}
      options={options}
      ariaLabel={labels.all}
      onChange={(next) => onChange(next as "all" | "on" | "off")}
      className="shrink-0"
    />
  );
};

export const StatTile: React.FC<{
  icon: React.ReactNode;
  num: number;
  label: string;
  onClick?: () => void;
  ariaLabel: string;
}> = ({ icon, num, label, onClick, ariaLabel }) => {
  const className = cn(
    "flex min-h-20 min-w-0 flex-1 items-center gap-3 rounded-[12px] border bg-bg-surface p-3 text-left shadow-card transition-[background-color,border-color] duration-[var(--duration-fast)] ease-[var(--easing-hover)]",
    onClick
      ? "cursor-pointer border-border-default hover:border-[var(--brand-500)] hover:bg-brand-tile-subtle focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-2"
      : "cursor-default border-border-card",
  );
  const content = (
    <>
      <span className="flex size-9 shrink-0 items-center justify-center text-fg-subtle">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-xl font-extrabold leading-[1.1] tabular-nums text-fg-default">
          {num}
        </span>
        <span className="mt-1 block truncate text-sm text-fg-muted">
          {label}
        </span>
      </span>
    </>
  );
  if (!onClick)
    return (
      <div aria-label={ariaLabel} className={className}>
        {content}
      </div>
    );
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className={className}
    >
      {content}
    </button>
  );
};

export const CopyKeyButton: React.FC<{ actionKey: string }> = ({
  actionKey,
}) => {
  const { t } = useTranslation("users");
  return (
    <AppTooltip content={t("accessDialog.copyKey", { key: actionKey })}>
      <Button
        size="2xs"
        variant="ghost"
        className="p-0.5 min-w-0 h-auto text-fg-muted shrink-0"
        aria-label={t("accessDialog.copyKey", { key: actionKey })}
        onClick={(event) => {
          event.stopPropagation();
          navigator.clipboard?.writeText(actionKey).catch(() => {});
        }}
      >
        <Copy size={12} aria-hidden="true" />
      </Button>
    </AppTooltip>
  );
};

export const InfoRow: React.FC<{
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}> = ({ icon, label, children }) => (
  <div className="flex min-w-0 items-start gap-3 rounded-lg border border-border-card bg-bg-surface px-3 py-2.5">
    <span className="grid size-9 shrink-0 place-items-center text-fg-muted">
      {icon}
    </span>
    <div className="min-w-0">
      <p className={DIALOG_DETAIL_LABEL_CLASSNAME}>{label}</p>
      <div className="mt-0.5 text-sm leading-5 font-medium text-fg-default">
        {children}
      </div>
    </div>
  </div>
);

export function accessChangeLabel(
  entry: SecurityAuditLogEntryRead,
  t: Translate,
): string {
  const metadata = (entry.event_metadata ?? {}) as Record<string, unknown>;
  const value = (key: string) =>
    typeof metadata[key] === "string" ? (metadata[key] as string) : undefined;
  const labels: Record<string, string> = {
    policy_assigned: "users:accessDialog.changeLog.policyAssigned",
    policy_revoked: "users:accessDialog.changeLog.policyRevoked",
    policy_action_revoked: "users:accessDialog.changeLog.policyActionRevoked",
    permission_granted: "users:accessDialog.changeLog.permissionGranted",
    permission_revoked: "users:accessDialog.changeLog.permissionRevoked",
    user_role_changed: "users:accessDialog.changeLog.roleChanged",
  };
  const key = labels[entry.event_type];
  if (!key) return entry.event_type;
  return t(key, {
    policyName: value("policy_name"),
    action: value("action"),
    by:
      value("assigned_by") ??
      value("revoked_by") ??
      value("granted_by") ??
      value("changed_by"),
    oldRole: value("old_role"),
    newRole: value("new_role"),
  });
}
