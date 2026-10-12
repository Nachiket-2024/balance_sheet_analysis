import React from "react";

import SearchInput from "../../ui/filters/SearchInput";
import LoadingState from "../../ui/feedback/LoadingState";
import FormAlert from "../../ui/feedback/FormAlert";
import ExpandCollapseAllButtons from "../../ui/navigation/ExpandCollapseAllButtons";
import { TabsContent } from "../../ui/shadcn/tabs";
import { cn } from "../../ui/styles/classNames";
import { isForbiddenError } from "../../api/apiError";
import { FilterSegment, type CatalogEntry, type Translate, type UserAccessState } from "./UserAccessDialogAtoms";
import { PermissionGroup } from "./UserAccessPermissionsParts";

// Permissions tab of the User Access dialog: search/filter and the
// resource-type-grouped permission list. Details and Policies tabs live in
// their own sibling files, composed together by UserAccessTabs.tsx - split
// out of one 540-line file, see AGENTS.md's ~350-line target.

interface UserAccessPermissionsTabProps {
  state: UserAccessState;
  locked: boolean;
  lockText?: string;
  totalGranted: number;
  catalog: CatalogEntry[];
  permissionRows: CatalogEntry[];
  permissionGroups: string[];
  t: Translate;
}

const UserAccessPermissionsTab: React.FC<UserAccessPermissionsTabProps> = ({
  state,
  locked,
  lockText,
  totalGranted,
  catalog,
  permissionRows,
  permissionGroups,
  t,
}) => (
  <TabsContent
    id="user-access-tabpanel-permissions"
    value="permissions"
    forceMount
    className={cn(
      "flex flex-col min-h-0 flex-1",
      state.tab !== "permissions" && "hidden",
    )}
  >
    <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-2 pt-3">
      <SearchInput
        value={state.permQuery}
        onChange={state.setPermQuery}
        resultsLabel={() => ""}
        loadingLabel={t("ui_text:loading")}
        placeholder={t("users:accessDialog.searchPermissions")}
        className="w-full sm:w-80"
      />
      <FilterSegment
        value={state.permFilter}
        onChange={state.setPermFilter}
        counts={{
          all: catalog.length,
          on: totalGranted,
          off: catalog.length - totalGranted,
        }}
        labels={{
          all: t("users:accessDialog.filterAll"),
          on: t("users:accessDialog.filterHasAccess"),
          off: t("users:accessDialog.filterNoAccess"),
        }}
      />
    </div>
    <div className="flex justify-end gap-2 mb-2">
      <ExpandCollapseAllButtons
        onExpandAll={state.expandAllPermGroups}
        onCollapseAll={state.collapseAllPermGroups}
      />
    </div>
    <div className="flex-1 min-h-0 overflow-y-auto pb-3 [scrollbar-gutter:stable]">
      {state.userPermissionsQuery.isLoading || state.catalogQuery.isLoading ? (
        <LoadingState
          message={t("users:permissionsDialog.loadingPermissions")}
        />
      ) : state.userPermissionsQuery.isError ? (
        <FormAlert status="error">
          {isForbiddenError(state.userPermissionsQuery.error)
            ? t("ui_text:notAuthorizedToView")
            : t("users:permissionsDialog.failedToLoad")}
        </FormAlert>
      ) : permissionRows.length === 0 ? (
        <p className="text-fg-muted">{t("users:accessDialog.noMatches")}</p>
      ) : (
        <div className="flex flex-col gap-3">
          {permissionGroups.map((group) => (
            <PermissionGroup
              key={group}
              group={group}
              items={permissionRows.filter(
                (entry) => entry.resource_type === group,
              )}
              state={state}
              locked={locked}
              lockText={lockText}
            />
          ))}
        </div>
      )}
    </div>
  </TabsContent>
);

export default UserAccessPermissionsTab;
