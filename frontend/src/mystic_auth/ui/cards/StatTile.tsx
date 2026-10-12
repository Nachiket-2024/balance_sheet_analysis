import React from "react";

import { Skeleton } from "../shadcn/skeleton";
import { cn } from "../styles/classNames";
import { useLanguageStore } from "../../store/languageStore";
import { formatNumber } from "../../translations/numerals";

interface StatTileProps {
    icon: React.ReactNode;
    label: string;
    value: number | undefined;
    isLoading: boolean;
    isError?: boolean;
    dotColor?: string;
    onClick?: () => void;
    ariaLabel?: string;
    pressed?: boolean;
}

/** Shared filterable summary tile used by the Users, Policies, Permissions,
 * and Rate Limits pages. Keeping the surface, icon treatment, hover state,
 * and pressed state here prevents page-specific drift. */
const StatTile: React.FC<StatTileProps> = ({
    icon,
    label,
    value,
    isLoading,
    isError = false,
    dotColor,
    onClick,
    ariaLabel,
    pressed = false,
}) => {
    const language = useLanguageStore((state) => state.chromeLanguage);
    const className = cn(
        "text-left flex items-center gap-3 flex-1 min-w-0 p-3 rounded-[12px] border shadow-card",
        "transition-[background-color,border-color] duration-[var(--duration-fast)] ease-[var(--easing-hover)]",
        onClick ? "cursor-pointer" : "cursor-default",
        pressed
            ? "bg-[var(--brand-200)] dark:bg-[color-mix(in_srgb,var(--brand-solid)_30%,transparent)] border-[var(--brand-500)]"
            : "bg-bg-surface border-border-default",
        onClick && !pressed && "hover:border-[var(--brand-500)] hover:bg-brand-tile-subtle",
        onClick && "focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-2",
    );

    const content = (
        <>
            <div className="size-[2.375rem] shrink-0 rounded-control bg-brand-tile-subtle border border-[var(--brand-500)] text-brand-fg flex items-center justify-center">
                {icon}
            </div>
            <div className="min-w-0">
                {isLoading ? (
                    <Skeleton className="h-6 w-12 bg-bg-muted" />
                ) : (
                    <p className="text-xl font-extrabold leading-[1.1] text-fg-default tabular-nums">
                        {isError || value === undefined ? "–" : formatNumber(value, language)}
                    </p>
                )}
                <div className="flex items-center gap-1.5 mt-1">
                    {dotColor && <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: dotColor }} />}
                    <p className={cn("text-sm truncate", pressed ? "text-fg-default" : "text-fg-muted")}>
                        {label}
                    </p>
                </div>
            </div>
        </>
    );

    if (!onClick) return <div aria-label={ariaLabel} className={className}>{content}</div>;

    return (
        <button type="button" onClick={onClick} aria-pressed={pressed} aria-label={ariaLabel} className={className}>
            {content}
        </button>
    );
};

export default StatTile;
