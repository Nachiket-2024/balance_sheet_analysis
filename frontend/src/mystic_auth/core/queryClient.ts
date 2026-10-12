import { QueryClient } from "@tanstack/react-query";

// Singleton TanStack Query client for all server state in the app. Exported at module
// level (not just inside a component) so code outside the React tree, specifically
// setupAuthInterceptor.ts, can write into the ["currentUser"] cache on an
// unrecoverable 401 without needing a hook.
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            retry: false,
            // Default of 0 makes every remount/refocus stale, causing duplicate
            // requests on nearly every navigation. 30s absorbs that while still
            // picking up another user's change within one page load.
            staleTime: 30 * 1000,
        },
    },
});
