import { create } from "zustand";

interface RouteLoadingState {
    /** Count of in-flight lazy route chunk imports, not a boolean: two navigations can
     * race (e.g. double-click), and the bar must stay visible until all of them settle,
     * not just the most recent one. */
    pendingCount: number;
}

// Tracks in-flight lazy route chunk loads so RouteProgressBar can show a
// top-of-viewport progress bar during a route transition, independent of Suspense's
// own fallback (RouteSkeleton, which rarely mounts, see trackedLazy.ts for why).
export const useRouteLoadingStore = create<RouteLoadingState>(() => ({
    pendingCount: 0,
}));

export function startRouteLoad(): void {
    useRouteLoadingStore.setState((s) => ({ pendingCount: s.pendingCount + 1 }));
}

export function finishRouteLoad(): void {
    useRouteLoadingStore.setState((s) => ({ pendingCount: Math.max(0, s.pendingCount - 1) }));
}
