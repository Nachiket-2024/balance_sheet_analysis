import React from "react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../shadcn/tooltip";

interface AppTooltipProps {
    /** Falsy content disables the tooltip entirely (renders children plain),
     * so callers can pass an optional string without an extra branch. */
    content?: React.ReactNode;
    children: React.ReactElement;
    openDelay?: number;
    /** Radix's Tooltip has no per-instance close delay (only Provider-level
     * skipDelayDuration, a shared "rapid re-hover" window) - this prop is
     * kept for API compatibility with every existing call site but has no
     * effect. The close fade is handled by the close animation's own
     * duration instead (see ui/shadcn/tooltip.tsx's data-[state=closed]
     * classes). */
    closeDelay?: number;
}

/**
 * Styled stand-in for the browser's native `title` attribute, which renders
 * as unstyled OS chrome. Wrap any element that needs a hover/focus hint
 * (truncated text, a disabled action's reason) instead of adding `title`.
 *
 * Overrides shadcn's default bg-foreground/text-background tooltip (an
 * inverted-contrast chip: solid black in light mode, solid white in dark
 * mode) with the same surface/border/text tokens as Card, so a tooltip
 * never flashes the opposite theme for an instant every time it opens.
 */
const AppTooltip: React.FC<AppTooltipProps> = ({ content, children, openDelay = 300 }) => {
    if (!content) return children;

    return (
        // Its own Provider, not a single one shared app-wide from main.tsx:
        // every existing call site (including in isolated component tests
        // that render just one component with no app-level provider tree)
        // expects AppTooltip to be self-contained. The tradeoff is losing
        // Radix's cross-tooltip "rapid re-hover" delay skip, not a
        // correctness issue.
        <TooltipProvider delayDuration={openDelay}>
            <Tooltip>
                {/* asChild clones the trigger's own data-state (open/closed)
                    onto its child. That clobbers Radix primitives that use
                    data-state for their own meaning, so the tooltip state
                    goes on this neutral span instead. It must be measurable:
                    display:contents gives Floating UI no box to anchor to,
                    which sends tooltips to the viewport origin. */}
                <TooltipTrigger asChild>
                    <span className="inline-flex min-w-0 max-w-full align-middle">
                        {children}
                    </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-80 text-center bg-bg-surface text-fg-default border border-border-default shadow-card [&>svg]:bg-bg-surface [&>svg]:fill-bg-surface">
                    {content}
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
};

export default AppTooltip;
