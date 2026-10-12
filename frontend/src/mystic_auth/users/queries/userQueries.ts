import { useQuery } from "@tanstack/react-query";

import { getUserStatsApi, listUsersApi } from "../../api/users_api";
import type { ManagedUserRead } from "../../api/users_api";
import type { SortDirection } from "../../ui/hooks/useSortState";

// Safety cap on "select all matching filters" (BulkActionToolbar): without
// one, a very broad filter (or none at all) could queue a bulk op against
// the entire user table in a single click. Same spirit as export_users'
// USER_EXPORT_MAX_ROWS - narrow the filters instead of raising this.
export const SELECT_ALL_MATCHING_MAX = 2000;

export const USERS_QUERY_KEY = ["users"] as const;
export const USER_STATS_QUERY_KEY = ["users", "stats"] as const;

export interface UsersPage {
    users: ManagedUserRead[];
    /** From the X-Total-Count response header; 0 if the header is somehow
     * missing rather than throwing, so a transient proxy/CORS misconfig
     * degrades to "no pages" instead of crashing the page. */
    total: number;
}

export interface UsersFilters {
    search?: string;
    role?: string;
    isVerified?: boolean;
    status?: string;
    policy?: string;
    permission?: string;
    permissionSource?: "policy" | "direct";
    lastLogin?: string;
    sortBy?: string;
    sortDir?: SortDirection;
}

export function useUsersQuery(page: number, pageSize: number, filters: UsersFilters = {}, enabled = true) {
    return useQuery<UsersPage>({
        queryKey: [...USERS_QUERY_KEY, page, pageSize, filters],
        queryFn: async () => {
            const res = await listUsersApi({
                limit: pageSize,
                offset: (page - 1) * pageSize,
                ...filters,
                search: filters.search || undefined,
            });
            const total = Number(res.headers["x-total-count"]);
            return { users: res.data, total: Number.isFinite(total) ? total : 0 };
        },
        // Keeps the current page's rows on screen while the next page loads
        // (same as auditQueries.ts), avoiding a loading-skeleton flash and
        // page-height shift on navigation.
        // CommandPalette reuses this hook to search users on-demand and
        // needs to skip the request entirely while its query is empty,
        // rather than fetching (and caching) an unfiltered first page.
        enabled,
    });
}

/** Fetches every email matching the given filters, not just the current
 * page, for BulkActionToolbar's "select all N matching filters". Pages
 * through listUsersApi at its own max page size (1000) since there's no
 * "give me just the emails" endpoint, stopping once it has everything the
 * X-Total-Count header reports. Throws once collection would exceed
 * SELECT_ALL_MATCHING_MAX, so a caller can tell the permission holder to narrow the
 * filters instead of silently truncating who gets acted on. */
export async function fetchAllMatchingUserEmails(filters: UsersFilters): Promise<string[]> {
    const PAGE_SIZE = 1000;
    const emails: string[] = [];
    let offset = 0;
    for (;;) {
        const res = await listUsersApi({ limit: PAGE_SIZE, offset, ...filters, search: filters.search || undefined });
        emails.push(...res.data.map((u) => u.email));
        if (emails.length > SELECT_ALL_MATCHING_MAX) {
            throw new Error(
                `This filter matches more than ${SELECT_ALL_MATCHING_MAX} users. Narrow the filters and try again.`
            );
        }
        const total = Number(res.headers["x-total-count"]);
        offset += PAGE_SIZE;
        if (!Number.isFinite(total) || emails.length >= total || res.data.length === 0) break;
    }
    return emails;
}

/** Aggregate counts for the Users page's summary card, independent of the
 * main list's current page/filters, so it stays put while those change.
 * `enabled` defaults true (UsersPage always wants it); OperationsShortcutsCard
 * passes false for a viewer without users:list_all, so mounting the
 * Dashboard alone doesn't fire GET /users/stats against a 403. */
export function useUserStatsQuery(enabled = true) {
    return useQuery({
        queryKey: USER_STATS_QUERY_KEY,
        queryFn: async () => {
            const res = await getUserStatsApi();
            return res.data;
        },
        enabled,
    });
}
