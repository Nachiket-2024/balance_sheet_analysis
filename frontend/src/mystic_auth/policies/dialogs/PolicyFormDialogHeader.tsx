import React from "react";
import { Lock, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { DialogHeader, DialogTitle } from "../../ui/shadcn/dialog";
import { DIALOG_HEADER_CLASSNAME } from "../../ui/styles/dialogStyles";
import type { PolicyRead } from "../../api/policies_api";
import Badge from "../../ui/badges/Badge";
import { displayAuthorizationDescription, PROTECTED_POLICY_NAMES, RESOURCE_TYPE_ICONS, resourceTypeIconTone } from "../policyCardHelpers";

const PolicyFormDialogHeader: React.FC<{ isEditing: boolean; policy?: PolicyRead }> = ({ isEditing, policy }) => {
  const { t } = useTranslation("policies");
  const ResourceIcon = policy ? (RESOURCE_TYPE_ICONS[policy.resource_type] ?? ShieldCheck) : ShieldCheck;
  return (
    <DialogHeader className={DIALOG_HEADER_CLASSNAME}>
      <div className="flex min-w-0 items-start gap-3">
        <ResourceIcon size={22} className={`mt-1 shrink-0 ${policy ? resourceTypeIconTone(policy.resource_type) : "text-fg-muted"}`} aria-hidden="true" />
        <div className="min-w-0">
          {policy && isEditing ? (
            <DialogTitle className="sr-only">{t("formDialog.editTitle")}</DialogTitle>
          ) : (
            <DialogTitle>{t("formDialog.createTitle")}</DialogTitle>
          )}
          {policy ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <p className="break-words text-sm font-medium text-fg-default">{policy.name}</p>
                {PROTECTED_POLICY_NAMES.has(policy.name) && (
                  <Badge colorPalette="gray" variant="subtle" size="sm">
                    <Lock size={12} aria-hidden="true" />
                    {t("columns.protected")}
                  </Badge>
                )}
              </div>
              <p className="mt-0.5 line-clamp-2 break-words text-sm text-fg-muted">
                {displayAuthorizationDescription(policy.description, t("detailsDialog.noDescription"))}
              </p>
            </>
          ) : (
            <p className="text-sm text-fg-muted">{t("formDialog.dialogSubtitle")}</p>
          )}
        </div>
      </div>
    </DialogHeader>
  );
};

export default PolicyFormDialogHeader;
