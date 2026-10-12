import React from "react";

import { Skeleton } from "../ui/shadcn/skeleton";

interface PermissionsGroupSkeletonProps {
    label: string;
    groupCount?: number;
}

/**
 * Loading treatment for the permission catalog's collapsed resource cards.
 * It keeps the same card rhythm and approximate header height as the loaded
 * groups, so the page does not jump when the catalog request resolves.
 */
const PermissionsGroupSkeleton: React.FC<PermissionsGroupSkeletonProps> = ({ label, groupCount = 5 }) => (
    <div className="flex flex-col gap-4" role="status" aria-label={label}>
        {Array.from({ length: groupCount }).map((_, index) => (
            <div
                key={index}
                className="flex items-center justify-between rounded-2xl border border-border-card bg-bg-surface/70 p-3 shadow-card sm:p-4"
            >
                <div className="flex min-w-0 flex-1 items-center gap-2">
                    <Skeleton className="size-4 shrink-0 rounded-sm" />
                    <Skeleton className="h-4 w-28 max-w-[32%]" />
                </div>
                <div className="flex shrink-0 items-center gap-3 ps-3">
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-16" />
                    <Skeleton className="size-8 rounded-md" />
                </div>
            </div>
        ))}
    </div>
);

export default PermissionsGroupSkeleton;
