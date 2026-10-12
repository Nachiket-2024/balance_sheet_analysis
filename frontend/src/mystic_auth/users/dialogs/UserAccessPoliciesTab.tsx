import React from "react";
import { ChevronRight } from "lucide-react";

import SearchInput from "../../ui/filters/SearchInput";
import LoadingState from "../../ui/feedback/LoadingState";
import FormAlert from "../../ui/feedback/FormAlert";
import AppTooltip from "../../ui/feedback/AppTooltip";
import ExpandCollapseAllButtons from "../../ui/navigation/ExpandCollapseAllButtons";
import { Switch } from "../../ui/shadcn/switch";
import { TabsContent } from "../../ui/shadcn/tabs";
import { cn } from "../../ui/styles/classNames";
import { isForbiddenError } from "../../api/apiError";
import { IfCan } from "../../authorization/IfCan";
import { useAuthorization } from "../../authorization/useAuthorization";
import { PERMISSIONS } from "../../authorization/permissions";
import { canGrantPolicy } from "../../authorization/grantability";
import { policyAddsNothingNew } from "../../policies/logic/effectiveGrants";
import {
  displayAuthorizationDescription,
  PROTECTED_POLICY_NAMES,
  RESOURCE_TYPE_ICONS,
  resourceTypeIconTone,
} from "../../policies/policyCardHelpers";
import { FilterSegment, type CatalogEntry, type Translate, type UserAccessState } from "./UserAccessDialogAtoms";
import { PolicyActionsTable } from "./UserAccessDialogParts";

// Policies tab of the User Access dialog: search/filter, the expandable
// policy list, and per-policy assign/revoke. Details and Permissions tabs
// live in their own sibling files, composed together by UserAccessTabs.tsx -
// split out of one 540-line file, see AGENTS.md's ~350-line target.

type PolicyEntry = {
  name: string;
  description?: string | null;
  actions: string[];
  resource_type: string;
};

interface UserAccessPoliciesTabProps {
  state: UserAccessState;
  locked: boolean;
  lockText?: string;
  allPolicies: PolicyEntry[];
  policyRows: PolicyEntry[];
  catalog: CatalogEntry[];
  t: Translate;
}

const UserAccessPoliciesTab: React.FC<UserAccessPoliciesTabProps> = ({
  state,
  locked,
  lockText,
  allPolicies,
  policyRows,
  catalog,
  t,
}) => {
  const { can } = useAuthorization();
  const isSelfProtectedPolicy = (name: string) =>
    state.isSelf && PROTECTED_POLICY_NAMES.has(name);
  return (
    <TabsContent
      id="user-access-tabpanel-policies"
      value="policies"
      forceMount
      className={cn(
        "flex flex-col min-h-0 flex-1",
        state.tab !== "policies" && "hidden",
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-2 pt-3">
        <SearchInput
          value={state.polQuery}
          onChange={state.setPolQuery}
          resultsLabel={() => ""}
          loadingLabel={t("ui_text:loading")}
          placeholder={t("users:accessDialog.searchPolicies")}
          className="w-full sm:w-80"
        />
        <FilterSegment
          value={state.polFilter}
          onChange={state.setPolFilter}
          counts={{
            all: allPolicies.length,
            on: state.assignedPolicies.length,
            off: allPolicies.length - state.assignedPolicies.length,
          }}
          labels={{
            all: t("users:accessDialog.filterAll"),
            on: t("users:accessDialog.filterAssigned"),
            off: t("users:accessDialog.filterNotAssigned"),
          }}
        />
      </div>
      <div className="flex justify-end gap-2 mb-2">
        <ExpandCollapseAllButtons
          onExpandAll={state.expandAllPolicies}
          onCollapseAll={state.collapseAllPolicies}
        />
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto pb-3 [scrollbar-gutter:stable]">
        {state.userPoliciesQuery.isLoading ||
        state.allPoliciesQuery.isLoading ? (
          <LoadingState message={t("users:policiesDialog.loadingPolicies")} />
        ) : state.userPoliciesQuery.isError ? (
          <FormAlert status="error">
            {isForbiddenError(state.userPoliciesQuery.error)
              ? t("ui_text:notAuthorizedToView")
              : t("users:policiesDialog.failedToLoad")}
          </FormAlert>
        ) : policyRows.length === 0 ? (
          <p className="text-fg-muted">{t("users:accessDialog.noMatches")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            {policyRows.map((policy) => {
              const assigned = state.assignedNames.has(policy.name);
              const open = state.polOpen.has(policy.name);
              const selfProtected =
                assigned && isSelfProtectedPolicy(policy.name);
              const covered =
                !assigned &&
                policyAddsNothingNew(policy, state.effectiveGrantKeys);
              const ungrantable = !canGrantPolicy(policy, can);
              const disabled = locked || selfProtected || covered || ungrantable;
              const disabledReason = locked
                ? lockText
                : selfProtected
                  ? t("users:accessDialog.selfProtectedPolicyLocked")
                  : covered
                    ? t("users:accessDialog.policyAlreadyCovered")
                    : ungrantable
                      ? t("users:accessDialog.cannotGrantPolicy", {
                          defaultValue: "You must already hold every permission in this policy before you can assign or revoke it.",
                        })
                    : undefined;
              const canTogglePolicy =
                !disabled &&
                !ungrantable &&
                can(
                  assigned
                    ? PERMISSIONS.POLICIES_REVOKE
                    : PERMISSIONS.POLICIES_ASSIGN,
                );
              const ResourceIcon =
                RESOURCE_TYPE_ICONS[policy.resource_type] ??
                RESOURCE_TYPE_ICONS["*"];
              return (
                <div key={policy.name}>
                  <div
                    className={cn(
                      "flex items-start gap-3 min-h-11 px-3 py-2.5 border border-border-default rounded-t-lg bg-bg-table-header cursor-pointer",
                      open ? "rounded-b-none border-b-0" : "rounded-b-lg",
                    )}
                    onClick={() => {
                      if (canTogglePolicy) state.togglePolicy(policy.name);
                    }}
                  >
                    <button
                      type="button"
                      className="mt-0.5 shrink-0 rounded-sm focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-2"
                      aria-expanded={open}
                      aria-label={
                        open
                          ? t(
                              "users:policiesDialog.collapseActionsAriaLabel",
                              { policyName: policy.name },
                            )
                          : t("users:policiesDialog.expandActionsAriaLabel", {
                              policyName: policy.name,
                            })
                      }
                      onClick={(event) => {
                        event.stopPropagation();
                        state.togglePolicyOpen(policy.name);
                      }}
                    >
                      <ChevronRight
                        size={16}
                        aria-hidden="true"
                        style={{
                          transform: open ? "rotate(90deg)" : undefined,
                        }}
                      />
                    </button>
                    <ResourceIcon
                      size={18}
                      className={cn(
                        "mt-0.5 shrink-0",
                        resourceTypeIconTone(policy.resource_type),
                      )}
                      aria-hidden="true"
                    />
                    <div className="flex min-w-0 flex-1 flex-col">
                      <p className="text-sm font-medium break-words">
                        {policy.name}
                      </p>
                      <p
                        className="line-clamp-2 text-[13px] leading-5 text-fg-muted"
                        title={policy.description ?? undefined}
                      >
                        {displayAuthorizationDescription(
                          policy.description,
                          t("users:accessDialog.actionCount", {
                            count: policy.actions.length,
                          }),
                        )}
                      </p>
                    </div>
                    <IfCan
                      action={
                        assigned ? "policies:revoke" : "policies:assign"
                      }
                    >
                      {disabledReason ? (
                        <AppTooltip content={disabledReason}>
                          <span
                            className="inline-flex"
                            title={disabledReason}
                          >
                            <Switch
                              checked={assigned}
                              disabled={disabled}
                              aria-label={policy.name}
                            />
                          </span>
                        </AppTooltip>
                      ) : (
                        <Switch
                          checked={assigned}
                          onClick={(event) => event.stopPropagation()}
                          onCheckedChange={() =>
                            state.togglePolicy(policy.name)
                          }
                          aria-label={
                            assigned
                              ? t("users:policiesDialog.revokeAriaLabel", {
                                  policyName: policy.name,
                                })
                              : policy.name
                          }
                        />
                      )}
                    </IfCan>
                  </div>
                  {open && (
                    <div className="border border-border-default rounded-b-lg">
                      <PolicyActionsTable
                        policy={policy}
                        assigned={assigned}
                        locked={locked}
                        selfProtected={selfProtected}
                        lockText={lockText}
                        catalog={catalog}
                        state={state}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </TabsContent>
  );
};

export default UserAccessPoliciesTab;
