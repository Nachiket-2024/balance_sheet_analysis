import React from "react";
import { useTranslation } from "react-i18next";

import { Button } from "../../ui/buttons/Button";
import SearchInput from "../../ui/filters/SearchInput";
import { Switch } from "../../ui/shadcn/switch";
import { IfCan } from "../../authorization/IfCan";
import { PERMISSIONS } from "../../authorization/permissions";
import type { PolicyRead } from "../../api/policies_api";
import {
  RESOURCE_TYPE_ICONS,
  formatResourceTypeLabel,
  resourceTypeIconTone,
} from "../../policies/policyCardHelpers";
import { groupPoliciesByResourceType } from "../../policies/policyListHelpers";
import { cn } from "../../ui/styles/classNames";

interface BulkPolicyTabProps {
  policies: PolicyRead[];
  selectedPolicies: string[];
  policySearch: string;
  isAssigning: boolean;
  isRemoving: boolean;
  onSearchChange: (value: string) => void;
  onToggle: (policyName: string, checked: boolean) => void;
  onRun: (remove: boolean) => void;
}

const BulkPolicyTab: React.FC<BulkPolicyTabProps> = ({
  policies,
  selectedPolicies,
  policySearch,
  isAssigning,
  isRemoving,
  onSearchChange,
  onToggle,
  onRun,
}) => {
  const { t } = useTranslation(["users", "ui_text"]);
  const query = policySearch.trim().toLowerCase();
  const shownPolicies = policies.filter(
    (policy) =>
      !query ||
      policy.name.toLowerCase().includes(query) ||
      policy.description?.toLowerCase().includes(query),
  );
  const policyGroups = groupPoliciesByResourceType(shownPolicies);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <SearchInput
        value={policySearch}
        onChange={onSearchChange}
        placeholder={t("users:accessDialog.searchPolicies")}
        resultsLabel={() => ""}
        loadingLabel={t("ui_text:loading")}
        className="w-full"
      />
      <div
        className="min-h-0 flex-1 grid grid-cols-1 gap-2 overflow-y-auto p-1 sm:grid-cols-2 [scrollbar-gutter:stable]"
        role="group"
        aria-label={t("users:policiesDialog.selectPolicyAriaLabel")}
      >
        {policyGroups.map(([resourceType, groupedPolicies]) => (
          <React.Fragment key={resourceType}>
            <h3 className="col-span-full sticky top-0 z-10 border-b border-border-default bg-bg-canvas/95 px-1 py-1 text-xs font-semibold uppercase tracking-wide text-fg-muted backdrop-blur-sm">
              {formatResourceTypeLabel(resourceType)} ({groupedPolicies.length})
            </h3>
            {groupedPolicies.map((policy) => (
          <label
            key={policy.name}
            className="flex min-w-0 cursor-pointer items-start gap-3 rounded-lg border border-border-default bg-bg-surface px-3 py-2.5"
          >
            {(() => {
              const ResourceIcon =
                RESOURCE_TYPE_ICONS[policy.resource_type] ??
                RESOURCE_TYPE_ICONS["*"];
              return (
                <ResourceIcon
                  size={18}
                  className={cn(
                    "mt-0.5 shrink-0",
                    resourceTypeIconTone(policy.resource_type),
                  )}
                  aria-hidden="true"
                />
              );
            })()}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {policy.name}
              </span>
              <span className="mt-1 block line-clamp-2 text-xs text-fg-muted">
                {policy.description ||
                  t("users:accessDialog.actionCount", {
                    count: policy.actions.length,
                  })}
              </span>
            </span>
            <Switch
              checked={selectedPolicies.includes(policy.name)}
              onCheckedChange={(checked) => onToggle(policy.name, !!checked)}
              aria-label={policy.name}
            />
          </label>
            ))}
          </React.Fragment>
        ))}
      </div>
      {!shownPolicies.length && (
        <p className="text-sm text-fg-muted">
          {t("users:accessDialog.noMatches")}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="brand"
          onClick={() => onRun(false)}
          disabled={!selectedPolicies.length}
          loading={isAssigning}
        >
          {t("users:bulkActions.assignToSelected")}
        </Button>
        <IfCan action={PERMISSIONS.POLICIES_REVOKE}>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onRun(true)}
            disabled={!selectedPolicies.length}
            loading={isRemoving}
          >
            {t("users:bulkActions.removeFromSelected")}
          </Button>
        </IfCan>
      </div>
    </div>
  );
};

export default BulkPolicyTab;
