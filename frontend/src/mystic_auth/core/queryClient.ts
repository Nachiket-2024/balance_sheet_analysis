import { QueryClient } from "@tanstack/react-query";

/**
 * Singleton TanStack Query client for all server state in the app. Exported as a module-level
 * singleton (rather than only living inside a component) so code outside the React tree,
 * specifically auth/setupAuthInterceptor.ts, which needs to write directly into the
 * ["currentUser"] query cache on an unrecoverable 401, can reach it without a hook.
 */
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            retry: false,
        },
    },
});
