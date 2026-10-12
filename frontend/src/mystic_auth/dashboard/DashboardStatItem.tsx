import React from "react";
import { ArrowDown } from "lucide-react";

import { cn } from "../ui/styles/classNames";

interface DashboardStatItemProps {
    icon: React.ReactNode;
    label: string;
    /** A plain string/number, or a richer node (Previous login passes date
     * plus a muted time, see DashboardIdentityCard). */
    value: React.ReactNode;
    /** Makes the whole stat a button. Used by Active sessions to jump to the
     * sessions table further down the page. */
    onClick?: () => void;
    /** Accessible name for the button form, since label + value alone
     * doesn't say what clicking does. */
    actionLabel?: string;
}

/** One icon + label/value stat, inline (no border/bg of its own) so it sits
 * directly in DashboardIdentityCard's identity row. The icon is plain and
 * muted: these are read-only metadata, not actions. The one clickable stat
 * gets a small arrow and a brand-colored hover so it reads as a link without
 * looking like a separate button. */
const DashboardStatItem: React.FC<DashboardStatItemProps> = ({ icon, label, value, onClick, actionLabel }) => {
    const content = (
        <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-9 h-9 shrink-0 text-fg-subtle flex items-center justify-center">
                {icon}
            </div>
            <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-wide text-fg-muted whitespace-nowrap">
                    {label}
                </p>
                <div className="stat-value flex items-center gap-1 text-base font-semibold text-fg-default leading-[1.3]">
                    <div>{value}</div>
                    {onClick && <ArrowDown size={14} aria-hidden="true" color="var(--fg-muted)" />}
                </div>
            </div>
        </div>
    );

    if (!onClick) return content;

    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={actionLabel}
            className={cn(
                "text-left cursor-pointer rounded-control",
                // Negative margin cancels the padding so the stat stays aligned
                // with its non-clickable siblings while the hover area is roomier.
                "px-2 py-1 -mx-2 -my-1",
                "transition-[background-color,border-color,color] duration-[var(--duration-hover)] ease-[var(--easing-hover)]",
                "hover:bg-brand-subtle [&:hover_.stat-value]:text-brand-fg",
                "focus-visible:outline-2 focus-visible:outline-brand-focus-ring focus-visible:outline-offset-2"
            )}
        >
            {content}
        </button>
    );
};

export default DashboardStatItem;
