import React, { useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { useTranslation } from "react-i18next";

import StyledSelect from "../ui/filters/StyledSelect";
import GroupedSearchSelect, { type GroupedSearchOptionGroup } from "../ui/filters/GroupedSearchSelect";
import FilterPanel from "../ui/cards/FilterPanel";
import SearchInput from "../ui/filters/SearchInput";
import FilterChips, { type FilterChip } from "../ui/filters/FilterChips";
import { PERMISSIONS } from "../authorization/permissions";
import { isDestructiveAction } from "../authorization/destructiveActions";
import { usePoliciesQuery } from "../policies/queries/policyQueries";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "../policies/policyCardHelpers";
import { ROLE_OPTIONS, capitalize } from "./usersColumns";

export const ALL_VALUE = "";

interface UsersFilterBarProps {
    search: string;
    setSearch: (v: string) => void;
    role: string;
    setRole: (v: string) => void;
    verified: string;
    setVerified: (v: string) => void;
    status: string;
    setStatus: (v: string) => void;
    policy: string;
    setPolicy: (v: string) => void;
    permission: string;
    setPermission: (v: string) => void;
    permissionSource?: "policy" | "direct";
    lastLogin: string;
    setLastLogin: (v: string) => void;
    /** True for every in-flight request the search/filters drive, not just
     * the very first one - see useUsersPageState's isFetching. Drives the
     * spinner next to the search box, since the previous page's rows stay
     * on screen (keepPreviousData) with no other visual sign a request is
     * running. */
    isFetching: boolean;
    /** Total matching rows across every page, from the same response the
     * table renders from - shown next to the search box so the user has
     * some confirmation their search/filters actually did something, even
     * when the visible rows alone don't make that obvious (e.g. a filter
     * that doesn't change which rows are on the current page). */
    totalResults: number | undefined;
    onClearFilters: () => void;
}

/** UsersPage's search box plus role/verified/status/policy/permission
 * filters. Split out of UsersPage.tsx like audit_log/*\/*FilterBar.tsx:
 * owns only the controls, UsersPage owns the state and server query.
 * Policy and permission are two different views of the same PBAC
 * assignment (which policy a user holds vs. which action that policy
 * grants); see user_base_crud.py's _apply_filters for how each maps onto
 * the user_policies/policies join. */
const UsersFilterBar: React.FC<UsersFilterBarProps> = ({
    search, setSearch, role, setRole, verified, setVerified, status, setStatus,
    policy, setPolicy, permission, setPermission, permissionSource, lastLogin, setLastLogin, isFetching, totalResults,
    onClearFilters,
}) => {
    const { t } = useTranslation(["users", "ui_text"]);
    // Keep the page compact by default. Active filters remain visible as
    // chips, while the full control set is revealed only on demand.
    const [filtersOpen, setFiltersOpen] = useState(false);
    // Full policy list (same query UserPoliciesDialog's "assign a policy"
    // dropdown uses) so the Policy filter shows real names, not a stale list.
    const { data: policies, isLoading: isPoliciesLoading } = usePoliciesQuery();
    // Same pattern as AuthorizationFilterBar/PoliciesFilterBar's action
    // picker: PERMISSIONS already runs well past 20 flat values, so a plain
    // StyledSelect here meant an un-searchable, un-grouped wall of options.
    const permissionGroups = useMemo<GroupedSearchOptionGroup[]>(() => {
        const groups = new Map<string, GroupedSearchOptionGroup>();
        for (const action of Object.values(PERMISSIONS)) {
            const resourceType = action.split(":")[0];
            const group = groups.get(resourceType) ?? {
                key: resourceType,
                label: formatResourceTypeLabel(resourceType),
                options: [],
            };
            group.options.push({ value: action, label: formatPolicyActionLabel(action), destructive: isDestructiveAction(action) });
            groups.set(resourceType, group);
        }
        return Array.from(groups.values());
    }, []);
    const policyGroups = useMemo<GroupedSearchOptionGroup[]>(() => {
        const groups = new Map<string, GroupedSearchOptionGroup>();
        for (const currentPolicy of policies ?? []) {
            const group = groups.get(currentPolicy.resource_type) ?? {
                key: currentPolicy.resource_type,
                label: formatResourceTypeLabel(currentPolicy.resource_type),
                options: [],
            };
            group.options.push({ value: currentPolicy.name, label: currentPolicy.name });
            groups.set(currentPolicy.resource_type, group);
        }
        return Array.from(groups.values())
            .sort((left, right) => left.label.localeCompare(right.label))
            .map((group) => ({ ...group, options: group.options.sort((left, right) => left.label.localeCompare(right.label)) }));
    }, [policies]);
    const chips: FilterChip[] = [
        ...(search ? [{ key: "search", label: `Search: ${search}`, onClear: () => setSearch("") }] : []),
        ...(permission !== ALL_VALUE ? [{ key: "permission", label: `Permission: ${formatPolicyActionLabel(permission)}`, onClear: () => setPermission(ALL_VALUE) }] : []),
        ...(permissionSource ? [{
            key: "permission-source",
            label: permissionSource === "policy" ? t("users:page.permissionViaPolicy") : t("users:page.permissionDirect"),
            onClear: () => setPermission(ALL_VALUE),
        }] : []),
        ...(role !== ALL_VALUE ? [{ key: "role", label: `Role: ${capitalize(role)}`, onClear: () => setRole(ALL_VALUE) }] : []),
        ...(verified !== ALL_VALUE ? [{
            key: "verified",
            label: verified === "true" ? t("users:page.verified") : t("users:page.unverified"),
            onClear: () => setVerified(ALL_VALUE),
        }] : []),
        ...(status !== ALL_VALUE ? [{
            key: "status",
            label: status === "active" ? t("ui_text:active") : t("users:page.deactivated"),
            onClear: () => setStatus(ALL_VALUE),
        }] : []),
        ...(policy !== ALL_VALUE ? [{ key: "policy", label: `Policy: ${policy}`, onClear: () => setPolicy(ALL_VALUE) }] : []),
        ...(lastLogin !== ALL_VALUE ? [{
            key: "last-login",
            label: {
                today: t("users:page.lastLoginToday"),
                "7d": t("users:page.lastLogin7d"),
                "30d": t("users:page.lastLogin30d"),
                "90d": t("users:page.lastLogin90d"),
                never: t("users:page.lastLoginNever"),
            }[lastLogin] ?? lastLogin,
            onClear: () => setLastLogin(ALL_VALUE),
        }] : []),
    ];

    return (
        <FilterPanel>
            <div className="flex items-center gap-3 flex-wrap">
                <SearchInput
                    placeholder={t("users:page.searchPlaceholder")}
                    value={search}
                    onChange={setSearch}
                    isFetching={isFetching}
                    totalResults={totalResults}
                    resultsLabel={(count) => t("users:page.resultsCount", { count })}
                    loadingLabel={t("ui_text:loading")}
                />
                <button
                    type="button"
                    onClick={() => setFiltersOpen((open) => !open)}
                    aria-expanded={filtersOpen}
                    className="inline-flex h-9 items-center gap-2 rounded-md border border-border-default bg-bg-surface px-3 text-sm font-medium text-fg-muted transition-colors hover:border-[var(--brand-500)] hover:bg-brand-tile-subtle hover:text-brand-fg focus-visible:outline-2 focus-visible:outline-[var(--brand-500)] focus-visible:outline-offset-2"
                >
                    <SlidersHorizontal size={16} aria-hidden="true" />
                    {t("users:page.filters", { defaultValue: "Filters" })}
                    {chips.length > 0 && <span className="rounded-full bg-brand-solid px-1.5 text-xs text-white">{chips.length}</span>}
                </button>
            </div>

            {filtersOpen && <div className="flex items-center gap-3 flex-wrap">
                <GroupedSearchSelect
                    className="w-56"
                    ariaLabel={t("users:page.filterByPermission")}
                    value={permission}
                    onChange={setPermission}
                    isActive={permission !== ALL_VALUE}
                    groups={permissionGroups}
                    allValue={ALL_VALUE}
                    allLabel={t("users:page.allPermissions")}
                    searchPlaceholder={t("users:accessDialog.searchPermissions")}
                />
                <StyledSelect
                    className="w-36"
                    ariaLabel={t("users:page.filterByRole")}
                    value={role}
                    onChange={setRole}
                    isActive={role !== ALL_VALUE}
                    textTransform="capitalize"
                    options={[
                        { value: ALL_VALUE, label: t("users:page.allRoles") },
                        ...ROLE_OPTIONS.map((value) => ({ value, label: capitalize(value) })),
                    ]}
                />

                <StyledSelect
                    className="w-44"
                    ariaLabel={t("users:page.filterByVerified")}
                    value={verified}
                    onChange={setVerified}
                    isActive={verified !== ALL_VALUE}
                    options={[
                        { value: ALL_VALUE, label: t("users:page.allVerification") },
                        { value: "true", label: t("users:page.verified") },
                        { value: "false", label: t("users:page.unverified") },
                    ]}
                />

                <StyledSelect
                    className="w-36"
                    ariaLabel={t("users:page.filterByStatus")}
                    value={status}
                    onChange={setStatus}
                    isActive={status !== ALL_VALUE}
                    // Only "active" and "deleted" (deactivated) are reachable states:
                    // deactivating a user sets is_active=False and deleted_at=now
                    // together, in one step (see user_lifecycle_crud.py), so there's
                    // no separate "inactive but not deleted" row to filter for. The
                    // "deleted" query value is what the backend actually calls this
                    // state; the label here reads "Deactivated" to match the rest of
                    // the UI.
                    options={[
                        { value: ALL_VALUE, label: t("users:page.allStatuses") },
                        { value: "active", label: t("ui_text:active") },
                        { value: "deleted", label: t("users:page.deactivated") },
                    ]}
                />

                <GroupedSearchSelect
                    className="w-44"
                    ariaLabel={t("users:page.filterByPolicy")}
                    value={policy}
                    onChange={setPolicy}
                    isActive={policy !== ALL_VALUE}
                    groups={policyGroups}
                    allValue={ALL_VALUE}
                    allLabel={isPoliciesLoading ? t("ui_text:loading") : t("users:page.allPolicies")}
                    searchPlaceholder={t("users:accessDialog.searchPolicies")}
                />

                {/* Relative-bucket presets, same pattern as Okta/Auth0/
                 * Workspace permission-management consoles (design/users.html's
                 * lastLoginOpts): quick buckets cover the common cases at
                 * far less UI than a full custom date-range picker. */}
                <StyledSelect
                    className="w-40"
                    ariaLabel={t("users:page.filterByLastLogin")}
                    value={lastLogin}
                    onChange={setLastLogin}
                    isActive={lastLogin !== ALL_VALUE}
                    options={[
                        { value: ALL_VALUE, label: t("users:page.anyTime") },
                        { value: "today", label: t("users:page.lastLoginToday") },
                        { value: "7d", label: t("users:page.lastLogin7d") },
                        { value: "30d", label: t("users:page.lastLogin30d") },
                        { value: "90d", label: t("users:page.lastLogin90d") },
                        { value: "never", label: t("users:page.lastLoginNever") },
                    ]}
                />

            </div>}

            <FilterChips chips={chips} onClearAll={onClearFilters} />
        </FilterPanel>
    );
};

export default UsersFilterBar;
