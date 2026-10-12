import React from "react";

import { cn } from "../styles/classNames";

/** Shared surface for page filter controls, keeping the Users, Policies, and
 * Rate Limits filter cards visually aligned. */
const FilterPanel: React.FC<React.ComponentPropsWithoutRef<"div">> = ({ className, children, ...props }) => (
    <div className={cn("flex flex-col gap-3 rounded-2xl border border-border-card bg-bg-surface/70 p-3 shadow-card sm:p-4", className)} {...props}>
        {children}
    </div>
);

export default FilterPanel;
