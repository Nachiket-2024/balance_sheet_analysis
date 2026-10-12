import { useState } from "react";
import { useSearchParams } from "react-router";

import { useDebouncedValue } from "../ui/hooks/useDebouncedValue";
import { nextSortState } from "../ui/hooks/useSortState";
import { useUsersUiStore } from "./usersUiStore";
import { ALL_VALUE } from "./UsersFilterBar";

/** UsersPage's filter/sort state and URL sync (policy/permission deep
 * links), split out of useUsersPageState.ts to keep that file under the
 * repo's ~350-line target, see AGENTS.md. */
export function useUsersPageFilters() {
    // Read once, not synced back to the URL: only needed for deep links in
    // (CommandPalette navigates to /users?search=<email>).
    const [searchParams, setSearchParams] = useSearchParams();
    const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
    // Debounced since search now hits the server (the table is paginated,
    // not filtered client-side), so typing shouldn't fire one request per key.
    const debouncedSearch = useDebouncedValue(search);

    // Backed by useUsersUiStore, not local useState, so these survive leaving this page
    // and coming back - see accountSettingsUiStore.ts's matching comment. `search` is the
    // one exception, kept as local useState above (see usersUiStore.ts).
    const { role, verified, status, policy: storedPolicy, permission: storedPermission, lastLogin, sortKey, sortDir, update } = useUsersUiStore();
    const setRole = (value: string) => update({ role: value });
    const setVerified = (value: string) => update({ verified: value });
    const setStatus = (value: string) => update({ status: value });
    // Policy deep links are used by PoliciesPage's "View policy holders"
    // action. While a policy query parameter is present it is the source of
    // truth, so browser back/forward and refresh keep the selected policy.
    // Changing the filter updates both the session store and the URL so the
    // page never appears filtered by one value while the address bar says
    // another.
    const urlPolicy = searchParams.get("policy");
    const policy = urlPolicy ?? storedPolicy;
    const setPolicy = (value: string) => {
        update({ policy: value });
        if (urlPolicy !== null) {
            const nextParams = new URLSearchParams(searchParams);
            if (value === ALL_VALUE) nextParams.delete("policy");
            else nextParams.set("policy", value);
            setSearchParams(nextParams, { replace: true });
        }
    };
    const urlPermission = searchParams.get("permission");
    const urlPermissionSource = searchParams.get("permission_source");
    const permission = urlPermission ?? storedPermission;
    const permissionSource: "policy" | "direct" | undefined = urlPermissionSource === "policy" || urlPermissionSource === "direct"
        ? urlPermissionSource
        : undefined;
    const setPermission = (value: string) => {
        update({ permission: value });
        if (urlPermission !== null) {
            const nextParams = new URLSearchParams(searchParams);
            if (value === ALL_VALUE) {
                nextParams.delete("permission");
                nextParams.delete("permission_source");
            } else {
                nextParams.set("permission", value);
            }
            setSearchParams(nextParams, { replace: true });
        }
    };
    // Relative bucket only (today/7d/30d/90d/never) - design/users.html's
    // custom date-range option is left out here, the bucket presets cover
    // the same permission-management pattern (Okta/Auth0/Workspace) at far less UI.
    const setLastLogin = (value: string) => update({ lastLogin: value });
    const sort = { key: sortKey, direction: sortDir };
    const toggleSort = (key: string) => {
        const next = nextSortState(sort, key);
        update({ sortKey: next.key, sortDir: next.direction });
    };

    const hasActiveFilters = Boolean(search) || role !== ALL_VALUE || verified !== ALL_VALUE
        || status !== ALL_VALUE || policy !== ALL_VALUE || permission !== ALL_VALUE || permissionSource !== undefined || lastLogin !== ALL_VALUE;
    const clearFilters = () => {
        setSearch("");
        setRole(ALL_VALUE);
        setVerified(ALL_VALUE);
        setStatus(ALL_VALUE);
        setPolicy(ALL_VALUE);
        setPermission(ALL_VALUE);
        setLastLogin(ALL_VALUE);
    };

    return {
        search,
        setSearch,
        debouncedSearch,
        role,
        setRole,
        verified,
        setVerified,
        status,
        setStatus,
        policy,
        setPolicy,
        permission,
        permissionSource,
        setPermission,
        lastLogin,
        setLastLogin,
        sort,
        toggleSort,
        hasActiveFilters,
        clearFilters,
    };
}
