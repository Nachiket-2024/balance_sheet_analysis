import { lazy } from "react";
import type { ComponentType, LazyExoticComponent } from "react";

import { startRouteLoad, finishRouteLoad } from "../../store/routeLoadingStore";

/**
 * Same as React.lazy, but reports the import's in-flight state to
 * routeLoadingStore so RouteProgressBar can show a top-of-viewport progress
 * bar while the chunk loads. Tracked independently of the Suspense
 * boundary: route-change transitions are already deferred by react-router,
 * so App.tsx's Suspense fallback (RouteSkeleton) rarely mounts at all.
 */
export function trackedLazy<T extends ComponentType>(
    factory: () => Promise<{ default: T }>
): LazyExoticComponent<T> {
    return lazy(() => {
        startRouteLoad();
        return factory().finally(finishRouteLoad);
    });
}
