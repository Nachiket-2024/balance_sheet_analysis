import React from "react";

import type { SupportedLanguage } from "../../translations/translations";
import type { ManagedUserRead } from "../../api/users_api";
import type { Translate, CatalogEntry, UserAccessState } from "./UserAccessDialogAtoms";
import UserAccessDetailsTab from "./UserAccessDetailsTab";
import UserAccessPoliciesTab from "./UserAccessPoliciesTab";
import UserAccessPermissionsTab from "./UserAccessPermissionsTab";

// Composes the User Access dialog's three tabs (Details, Policies,
// Permissions), each in its own file - split out of one 540-line file, see
// AGENTS.md's ~350-line target.

type PolicyEntry = {
  name: string;
  description?: string | null;
  actions: string[];
  resource_type: string;
};

interface UserAccessTabsProps {
  user: ManagedUserRead;
  state: UserAccessState;
  language: SupportedLanguage;
  locked: boolean;
  lockText?: string;
  totalGranted: number;
  allPolicies: PolicyEntry[];
  policyRows: PolicyEntry[];
  permissionRows: CatalogEntry[];
  permissionGroups: string[];
  catalog: CatalogEntry[];
  t: Translate;
  navigate: (to: string) => void;
  onTabChange: (tab: "details" | "policies" | "permissions") => void;
}

const UserAccessTabs: React.FC<UserAccessTabsProps> = ({
  user,
  state,
  language,
  locked,
  lockText,
  totalGranted,
  allPolicies,
  policyRows,
  permissionRows,
  permissionGroups,
  catalog,
  t,
  navigate,
  onTabChange,
}) => (
  <>
    <UserAccessDetailsTab
      user={user}
      state={state}
      language={language}
      totalGranted={totalGranted}
      t={t}
      navigate={navigate}
      onTabChange={onTabChange}
    />
    <UserAccessPoliciesTab
      state={state}
      locked={locked}
      lockText={lockText}
      allPolicies={allPolicies}
      policyRows={policyRows}
      catalog={catalog}
      t={t}
    />
    <UserAccessPermissionsTab
      state={state}
      locked={locked}
      lockText={lockText}
      totalGranted={totalGranted}
      catalog={catalog}
      permissionRows={permissionRows}
      permissionGroups={permissionGroups}
      t={t}
    />
  </>
);

export default UserAccessTabs;
