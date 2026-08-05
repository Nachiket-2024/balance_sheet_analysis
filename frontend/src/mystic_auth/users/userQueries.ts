import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getUserStatsApi, listUsersApi } from "../api/users_api";
import type { AdminUserRead } from "../api/users_api";
import type { SortDirection } from "../ui/hooks/useSortState";

export const USERS_QUERY_KEY = ["users"] as const;
export const USER_STATS_QUERY_KEY = ["users", "stats"] as const;

export interface UsersPage {
    users: AdminUserRead[];
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
    sortBy?: string;
    sortDir?: SortDirection;
}

export function useUsersQuery(page: number, pageSize: number, filters: UsersFilters = {}) {
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
        // Keeps the current page's rows on screen while a different page
        // loads in, same reasoning as auditQueries.ts's identical option:
        // without it, switching pages would flash the table's loading
        // skeleton and could shift the page's height mid-navigation.
        placeholderData: keepPreviousData,
    });
}

/** Aggregate counts for the Users page's summary card - independent of the
 * main list's current page/filters, so it stays put while those change. */
export function useUserStatsQuery() {
    return useQuery({
        queryKey: USER_STATS_QUERY_KEY,
        queryFn: async () => {
            const res = await getUserStatsApi();
            return res.data;
        },
    });
}
