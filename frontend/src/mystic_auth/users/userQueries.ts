import { useQuery } from "@tanstack/react-query";

import { listUsersApi } from "../api/users_api";

export const USERS_QUERY_KEY = ["users"] as const;

export function useUsersQuery() {
    return useQuery({
        queryKey: USERS_QUERY_KEY,
        queryFn: async () => (await listUsersApi()).data,
    });
}
