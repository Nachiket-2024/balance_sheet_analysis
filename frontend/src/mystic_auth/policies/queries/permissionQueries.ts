import { useQuery } from "@tanstack/react-query";

import {
    getMyPermissionsApi,
    getPermissionCatalogApi,
    getPermissionCatalogUsageApi,
    getUserPermissionsApi,
} from "../../api/permissions_api";

export const MY_PERMISSIONS_QUERY_KEY = ["permissions", "me"] as const;
export const userPermissionsQueryKey = (userEmail: string) => ["permissions", "user", userEmail] as const;
export const PERMISSION_CATALOG_QUERY_KEY = ["permissions", "catalog"] as const;
export const PERMISSION_CATALOG_USAGE_QUERY_KEY = ["permissions", "catalog", "usage"] as const;

// Usage (who holds each action) changes whenever a policy or direct grant
// is edited elsewhere in the app - much more often than the catalog itself
// - so it gets a short staleTime rather than the catalog's 30-minute one,
// just enough to dedupe the stats/filter-bar/table/dialog's simultaneous
// reads of the same data on mount.
const PERMISSION_CATALOG_USAGE_STALE_TIME = 30 * 1000;

// The catalog is MysticAuth's built-in, code-defined vocabulary (backend's
// authorization/permissions_catalog.py) that only changes on deploy, so a
// long staleTime avoids refetching it on every unrelated remount/refocus.
const PERMISSION_CATALOG_STALE_TIME = 30 * 60 * 1000;

/** The full permission catalog: source for every action/resource_type
 * dropdown (UserAccessDialog, BulkUserAccessDialog,
 * PolicyFormDialog), PermissionsPage's browsable list, and
 * CommandPaletteResults' catalog search. `enabled` defaults true;
 * CommandPalette passes false for viewers who can't reach the Permissions
 * page, so mounting the palette alone doesn't fire the request. Shared
 * queryKey means whichever caller fetches first satisfies the rest from
 * cache. */
export function usePermissionCatalogQuery(enabled = true) {
    return useQuery({
        queryKey: PERMISSION_CATALOG_QUERY_KEY,
        queryFn: async () => (await getPermissionCatalogApi()).data,
        staleTime: PERMISSION_CATALOG_STALE_TIME,
        enabled,
    });
}

/** Who currently holds each catalog action (backend: GET /authorization/
 * permissions/catalog/usage), gated by permissions:read alone - only
 * PermissionsPage reads this, since its route already requires that
 * permission (see App.tsx), so there's no "enabled" off switch to wire up
 * unlike usePermissionCatalogQuery. */
export function usePermissionCatalogUsageQuery() {
    return useQuery({
        queryKey: PERMISSION_CATALOG_USAGE_QUERY_KEY,
        queryFn: async () => (await getPermissionCatalogUsageApi()).data,
        staleTime: PERMISSION_CATALOG_USAGE_STALE_TIME,
    });
}

export function useMyPermissionsQuery(enabled = true) {
    return useQuery({
        queryKey: MY_PERMISSIONS_QUERY_KEY,
        queryFn: async () => (await getMyPermissionsApi()).data,
        // See useMyPoliciesQuery's matching comment for why this needs an
        // off switch: UserDetailsDialog only wants it for the viewer's own
        // row. Defaults true so AccountStatusCard, which always wants it,
        // stays unchanged.
        enabled,
    });
}

export function useUserPermissionsQuery(userEmail: string, enabled = true) {
    return useQuery({
        queryKey: userPermissionsQueryKey(userEmail),
        queryFn: async () => (await getUserPermissionsApi(userEmail)).data,
        enabled: enabled && !!userEmail,
    });
}
