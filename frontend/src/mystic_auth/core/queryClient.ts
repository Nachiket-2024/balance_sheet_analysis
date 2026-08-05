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
            // Default was 0, so every remount (e.g. navigating away from and
            // back to a page) and every window refocus was treated as
            // "stale" and silently refetched in the background - harmless
            // for correctness (TanStack still shows cached data instantly)
            // but it meant duplicate network calls on nearly every
            // navigation, e.g. DashboardPage's own useCurrentUserQuery call
            // re-hitting GET /auth/me moments after App.tsx's root
            // useAuthSession call already had. 30s is short enough that
            // another admin's change (a role edit, a revoked policy) still
            // shows up within one page-load of it happening, while
            // absorbing the "tabbed away and back" and "navigated back to
            // this page" cases that don't need a fresh round-trip.
            staleTime: 30 * 1000,
        },
    },
});
