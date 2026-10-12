import React from "react";
import { FileText, Layers, ShieldCheck, TriangleAlert, UsersRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link as RouterLink } from "react-router";

import { isDestructiveAction } from "../authorization/destructiveActions";
import { PERMISSIONS } from "../authorization/permissions";
import { useCan } from "../authorization/useCan";
import {
  formatPolicyActionLabel,
  formatResourceTypeLabel,
  RESOURCE_TYPE_ICONS,
} from "../policies/policyCardHelpers";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/shadcn/dialog";
import { Button } from "../ui/buttons/Button";
import FormAlert from "../ui/feedback/FormAlert";
import {
  DIALOG_BODY_CLASSNAME,
  DIALOG_DETAIL_LABEL_CLASSNAME,
  DIALOG_DETAIL_VALUE_CLASSNAME,
  DIALOG_FOOTER_CLASSNAME,
  DIALOG_HEADER_CLASSNAME,
  DIALOG_PANEL_CLASSNAME,
  DIALOG_SECTION_CLASSNAME,
} from "../ui/styles/dialogStyles";
import type {
  PermissionCatalogEntry,
  PermissionUsageEntry,
} from "../api/permissions_api";

interface PermissionDetailsDialogProps {
  isOpen: boolean;
  entry: PermissionCatalogEntry | null;
  /** Undefined while GET .../catalog/usage is still loading/hasn't
   * resolved for this action - the dialog then shows "-" instead of 0 so
   * "held by nobody" and "still loading" never look the same. */
  usage: PermissionUsageEntry | undefined;
  usageLoading?: boolean;
  usageError?: boolean;
  usageForbidden?: boolean;
  onRetryUsage?: () => void;
  onClose: () => void;
}

interface DetailRowProps {
  label: string;
  children: React.ReactNode;
}

/** Same label/value layout as PolicyDetailsDialog's DetailRow. Shows what
 * the table's Description column truncates. */
const DetailRow: React.FC<DetailRowProps> = ({ label, children }) => (
  <div className="flex flex-col gap-0.5">
    <p className={DIALOG_DETAIL_LABEL_CLASSNAME}>{label}</p>
    <div className={DIALOG_DETAIL_VALUE_CLASSNAME}>{children}</div>
  </div>
);

interface DetailCardProps {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  className?: string;
}

const DetailCard: React.FC<DetailCardProps> = ({ icon, label, children, className }) => (
  <div className={`rounded-xl border border-border-card bg-bg-surface p-3 ${className ?? ""}`}>
    <div className="flex items-start gap-3">
      <span className="grid size-9 shrink-0 place-items-center text-fg-muted">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-fg-muted">{label}</p>
        <div className="mt-1 text-sm font-medium text-fg-default">{children}</div>
      </div>
    </div>
  </div>
);

/**
 * PermissionDetailsDialog
 * ----------------------------
 * Read-only "View" panel for one permission catalog entry. Beyond the
 * original action/resource type/description, adds who actually holds it
 * (design/permissions.html, .project/permissions-page-review.md): which
 * active policies grant it (linking to Policies, filtered to that
 * resource type) and a direct-vs-via-policy user count, backed by GET
 * /authorization/permissions/catalog/usage. A destructive banner replaces
 * the old inline red badge for actions isDestructiveAction flags, since
 * this dialog has the room for an explanation a table row doesn't.
 *
 * No per-user list (unlike the mockup's aspirational "Users who hold it"
 * row-by-row list): the usage endpoint intentionally returns counts, not
 * emails, to keep this read-only catalog view from becoming a second way
 * to browse individual users' access - UserAccessDialog already owns that.
 */
const PermissionDetailsDialog: React.FC<PermissionDetailsDialogProps> = ({
  isOpen,
  entry,
  usage,
  usageLoading = false,
  usageError = false,
  usageForbidden = false,
  onRetryUsage,
  onClose,
}) => {
  const { t } = useTranslation(["permissions", "ui_text"]);
  const canReadPolicies = useCan(PERMISSIONS.POLICIES_READ);
  const canListUsers = useCan(PERMISSIONS.USERS_LIST_ALL);
  if (!entry) return null;
  const destructive = isDestructiveAction(entry.action);
  const ResourceIcon = RESOURCE_TYPE_ICONS[entry.resource_type] ?? ShieldCheck;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        overlayClassName="backdrop-blur-[2px]"
        closeLabel={t("ui_text:closeDialog")}
        className={`sm:max-w-[45rem] max-h-[calc(100svh-1.5rem)] flex flex-col ${DIALOG_PANEL_CLASSNAME}`}
      >
        <DialogHeader className={`${DIALOG_HEADER_CLASSNAME} px-4 py-4 sm:px-6`}>
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand-solid text-brand-contrast">
              <ResourceIcon size={22} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <DialogTitle className="text-xl tracking-[-0.02em] break-words">
                {formatPolicyActionLabel(entry.action)}
              </DialogTitle>
            </div>
          </div>
        </DialogHeader>
        <div className={`${DIALOG_BODY_CLASSNAME} px-4 sm:px-6`}>
          <div className="flex flex-col gap-4">
            {destructive && (
              <div className="flex items-start gap-2 rounded-xl border border-red-500 bg-red-subtle p-3 text-sm text-fg-error">
                <p>{t("permissions:detailsDialog.destructiveWarning")}</p>
                <TriangleAlert
                  size={16}
                  aria-hidden="true"
                  style={{ flexShrink: 0, marginTop: 2 }}
                />
              </div>
            )}
            <div className="grid grid-cols-1 items-stretch gap-3 sm:grid-cols-2">
              <DetailCard icon={<Layers size={18} aria-hidden="true" />} label={t("permissions:detailsDialog.resourceType")} className="h-full">
                {formatResourceTypeLabel(entry.resource_type)}
              </DetailCard>
              <DetailCard icon={<FileText size={18} aria-hidden="true" />} label={t("permissions:detailsDialog.description")} className="h-full">
                <span className="font-normal leading-5" title={entry.description}>{entry.description}</span>
              </DetailCard>
            </div>
            <section className={DIALOG_SECTION_CLASSNAME}>
              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-9 shrink-0 place-items-center text-fg-muted">
                    <UsersRound size={18} aria-hidden="true" />
                  </span>
                  <p className={DIALOG_DETAIL_LABEL_CLASSNAME}>{t("permissions:detailsDialog.heldBy")}</p>
                </div>
                {usageError && (
                  <FormAlert status="warning">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p>{t(usageForbidden ? "permissions:page.holderInfoForbiddenTitle" : "permissions:detailsDialog.holderInfoErrorTitle")}</p>
                        <p className="font-normal">{t(usageForbidden ? "permissions:page.holderInfoForbiddenDescription" : "permissions:detailsDialog.holderInfoErrorDescription")}</p>
                      </div>
                      {onRetryUsage && (
                        <Button type="button" variant="secondary" size="sm" onClick={onRetryUsage}>
                          {t("permissions:page.retryHolderInfo")}
                        </Button>
                      )}
                    </div>
                  </FormAlert>
                )}
                <div className={DIALOG_DETAIL_VALUE_CLASSNAME}>
                  {usageLoading ? (
                    <span className="text-fg-muted">{t("permissions:detailsDialog.loadingHolderInfo")}</span>
                  ) : usageError ? (
                    <span className="text-fg-muted">{t("permissions:detailsDialog.holderInfoUnavailable")}</span>
                  ) : usage === undefined ? (
                    <span className="text-fg-muted">{"–"}</span>
                  ) : usage.total_user_count === 0 ? (
                    <span className="text-fg-muted">{t("permissions:detailsDialog.heldByNobody")}</span>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {[
                        {
                          label: t("permissions:detailsDialog.viaPolicy"),
                          count: usage.policy_user_count,
                          source: "policy" as const,
                        },
                        {
                          label: t("permissions:detailsDialog.directGrants"),
                          count: usage.direct_grant_count,
                          source: "direct" as const,
                        },
                      ].map(({ label, count, source }) => {
                        const href = `/users?permission=${encodeURIComponent(entry.action)}&permission_source=${source}`;
                        const content = (
                          <>
                            <span className="min-w-0 truncate text-xs font-semibold uppercase tracking-wide text-fg-muted">
                              {label}
                            </span>
                            <span className="text-base font-semibold text-fg-default">{count}</span>
                          </>
                        );
                        if (canListUsers && count > 0) {
                          return (
                            <RouterLink
                              key={source}
                              to={href}
                              aria-label={t("permissions:detailsDialog.openUsers", { label })}
                              className="flex min-h-16 items-center justify-between gap-3 rounded-lg border border-border-default bg-bg-surface px-3 py-2 transition-colors hover:border-[var(--brand-500)] hover:bg-brand-tile-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-fg"
                            >
                              {content}
                            </RouterLink>
                          );
                        }
                        return (
                          <div
                            key={source}
                            aria-disabled={canListUsers ? "true" : undefined}
                            className="flex min-h-16 items-center justify-between gap-3 rounded-lg border border-border-default bg-bg-surface px-3 py-2"
                          >
                            {content}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                <DetailRow label={t("permissions:detailsDialog.policies")}>
                  {usageLoading || usageError ? (
                    <span className="text-fg-muted">{usageLoading ? t("permissions:detailsDialog.loadingHolderInfo") : t("permissions:detailsDialog.holderInfoUnavailable")}</span>
                  ) : usage === undefined ? (
                    <span className="text-fg-muted">{"–"}</span>
                  ) : usage.policies.length === 0 ? (
                    <span className="text-fg-muted">
                      {t("permissions:detailsDialog.noPolicies")}
                    </span>
                  ) : (
                    <div className="border border-border-default rounded-md overflow-hidden">
                      <div className="flex flex-col">
                        {usage.policies.map((policy, i) => (
                          <div
                            // A permission can be associated with the same policy
                            // more than once in aggregated/legacy data; keep the
                            // row identity unique so React does not drop updates.
                            key={`${policy.name}-${i}`}
                            className={`flex justify-between items-center px-3 py-2 ${i === 0 ? "" : "border-t border-border-default"} ${i % 2 === 1 ? "bg-bg-subtle" : ""}`}
                          >
                            {canReadPolicies ? (
                              <RouterLink
                                to="/policies"
                                aria-label={t("permissions:detailsDialog.openPolicy", {
                                  name: policy.name,
                                })}
                                title={t("permissions:detailsDialog.openPolicy", {
                                  name: policy.name,
                                })}
                                className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-md px-3 py-2 -mx-3 -my-2 hover:bg-bg-subtle hover:text-brand-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-fg"
                              >
                                <span className="flex min-w-0 items-center gap-2">
                                  <ShieldCheck
                                    size={14}
                                    aria-hidden="true"
                                    color="var(--brand-fg)"
                                  />
                                  <span className="truncate font-medium">{policy.name}</span>
                                </span>
                                <span className="shrink-0 text-sm text-fg-muted">
                                  {t("permissions:detailsDialog.policyUserCount", {
                                    count: policy.user_count,
                                  })}
                                </span>
                              </RouterLink>
                            ) : (
                              <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
                                <span className="flex min-w-0 items-center gap-2">
                                  <ShieldCheck
                                    size={14}
                                    aria-hidden="true"
                                    color="var(--brand-fg)"
                                  />
                                  <span className="truncate font-medium">{policy.name}</span>
                                </span>
                                <span className="shrink-0 text-sm text-fg-muted">
                                  {t("permissions:detailsDialog.policyUserCount", {
                                    count: policy.user_count,
                                  })}
                                </span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </DetailRow>
              </div>
            </section>
          </div>
        </div>
        <DialogFooter className={DIALOG_FOOTER_CLASSNAME}>
          <Button onClick={onClose} variant="secondary">
            {t("ui_text:close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PermissionDetailsDialog;
