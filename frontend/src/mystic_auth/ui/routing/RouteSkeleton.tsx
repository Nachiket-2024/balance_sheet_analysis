import React from "react";

import { Skeleton } from "../shadcn/skeleton";

// Same non-default fill reasoning as DashboardIdentityCardSkeleton's own
// SKELETON_CLASSNAME: Skeleton's stock fill is indistinguishable from
// Card's "bg-bg-surface" background in dark mode.
const SKELETON_CLASSNAME = "bg-bg-muted";

/**
 * Suspense fallback for App.tsx's route-level code splitting, shown only for
 * the brief window before a lazy page chunk resolves. Shaped like a generic
 * page (title bar plus content blocks) rather than a bare spinner, so a
 * route that does suspend reads as "arriving," not a hard blank cut.
 */
const RouteSkeleton: React.FC = () => (
    <div data-route-loading="true" className="max-w-(--size-page-content) w-full py-2">
        <span role="status" className="sr-only">Loading page...</span>
        {/* density.sectionGap -> --spacing-6 (themeTokens.ts), same value
            PageContainer's own mb-(--spacing-section-gap) resolves to. */}
        <Skeleton className={`h-8 w-48 mb-(--spacing-section-gap) ${SKELETON_CLASSNAME}`} />
        <div className="flex flex-col gap-4">
            <Skeleton className={`h-32 rounded-card ${SKELETON_CLASSNAME}`} />
            <Skeleton className={`h-32 rounded-card ${SKELETON_CLASSNAME}`} />
        </div>
    </div>
);

export default RouteSkeleton;
