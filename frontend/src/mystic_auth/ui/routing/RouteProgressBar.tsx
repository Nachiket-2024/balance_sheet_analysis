import React from "react";

import { useRouteLoadingStore } from "../../store/routeLoadingStore";

/**
 * Thin indeterminate progress bar pinned to the top of the viewport,
 * mounted once at the app root. Shown while a lazy route chunk is loading
 * (trackedLazy.ts/routeLoadingStore.ts) - overlays the current page instead
 * of a full-screen Suspense fallback blanking the app.
 */
const RouteProgressBar: React.FC = () => {
    const isLoading = useRouteLoadingStore((s) => s.pendingCount > 0);

    if (!isLoading) return null;

    return (
        // z-[2147483647]: the maximum value a 32-bit z-index can hold, so
        // this still overlays literally everything. The keyframes and
        // the bar's animation/box-shadow live in theme/tailwind.css as
        // .mystic-route-progress-bar - see that file for why (a strict
        // hash-only CSP can't allow a runtime-injected <style> tag).
        <div
            className="fixed top-0 left-0 right-0 h-1 z-[2147483647] overflow-hidden pointer-events-none"
            role="progressbar"
            aria-label="Loading"
            aria-valuetext="Loading"
        >
            <div className="mystic-route-progress-bar absolute top-0 left-0 h-full w-2/5 bg-brand-solid" />
        </div>
    );
};

export default RouteProgressBar;
