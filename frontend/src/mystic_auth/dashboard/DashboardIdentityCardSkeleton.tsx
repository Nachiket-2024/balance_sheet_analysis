import React from "react";

import { Skeleton } from "../ui/shadcn/skeleton";
import { Separator } from "../ui/shadcn/separator";
import { cn } from "../ui/styles/classNames";

// shadcn Skeleton's default fill is the same as Card's own background in
// dark mode (see theme/system.ts), so it's invisible even mid-pulse.
// "bg-bg-muted" reads as a visibly distinct block in both modes.
const SKELETON_CLASSNAME = "bg-bg-muted";

interface DashboardIdentityCardSkeletonProps {
    /** Announced to screen readers via a visually-hidden role="status" node,
     * since the shimmering boxes carry no signal for anyone not seeing
     * them. */
    loadingLabel: string;
}

/**
 * Loading placeholder for DashboardPage's identity card, shaped like its
 * loaded state (avatar + name/badge + email with three action buttons on
 * one row, then three stat tiles below a divider) instead of a generic
 * spinner, so the layout doesn't jump once the real data arrives.
 */
const DashboardIdentityCardSkeleton: React.FC<DashboardIdentityCardSkeletonProps> = ({ loadingLabel }) => (
    <div>
        <span role="status" className="sr-only">{loadingLabel}</span>
        <div className="flex items-center justify-between flex-wrap gap-x-5 gap-y-4">
            <div className="flex items-center gap-4">
                <Skeleton className={cn("w-14 h-14 shrink-0 rounded-full", SKELETON_CLASSNAME)} />
                <div>
                    <div className="flex items-center gap-2">
                        <Skeleton className={cn("h-5 w-36", SKELETON_CLASSNAME)} />
                        <Skeleton className={cn("h-5 w-16 rounded-full", SKELETON_CLASSNAME)} />
                    </div>
                    <Skeleton className={cn("h-4 w-48 mt-2", SKELETON_CLASSNAME)} />
                </div>
            </div>

            <div className="flex flex-row gap-2 shrink-0">
                <Skeleton className={cn("h-8 w-32 rounded-md", SKELETON_CLASSNAME)} />
                <Skeleton className={cn("h-8 w-28 rounded-md", SKELETON_CLASSNAME)} />
                <Skeleton className={cn("h-8 w-28 rounded-md", SKELETON_CLASSNAME)} />
            </div>
        </div>

        <Separator className="my-5" />

        <div className="flex items-center flex-wrap gap-x-6 gap-y-3">
            {["w-28", "w-24", "w-32"].map((w, i) => (
                <div key={i} className="flex items-center gap-2.5">
                    <Skeleton className={cn("w-9 h-9 rounded-md", SKELETON_CLASSNAME)} />
                    <div className="flex flex-col gap-1">
                        <Skeleton className={cn("h-3", w, SKELETON_CLASSNAME)} />
                        <Skeleton className={cn("h-4 w-16", SKELETON_CLASSNAME)} />
                    </div>
                </div>
            ))}
        </div>
    </div>
);

export default DashboardIdentityCardSkeleton;
