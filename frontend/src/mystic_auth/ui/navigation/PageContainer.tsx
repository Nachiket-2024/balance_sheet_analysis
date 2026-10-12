import React from "react";
import type { LucideIcon } from "lucide-react";

import Breadcrumbs, { type BreadcrumbEntry } from "./Breadcrumbs";
import { cn } from "../styles/classNames";

interface PageContainerProps {
    title: string;
    /** Renders a Breadcrumbs trail above the title when given a non-empty
     * array - omit for no breadcrumb bar, which every current page uses
     * (the built-in nav is flat, no nested detail routes yet). Wired here so
     * the first nested/detail page can adopt it without a new pattern. */
    breadcrumbs?: BreadcrumbEntry[];
    /** Same lucide-react icon assigned to this feature's NavItem
     * (navItems.ts), so the sidebar entry and page title share one glyph.
     * Optional - omit for a bare text title. */
    icon?: LucideIcon;
    /** Rendered directly after the title, inline in the same row - e.g. a
     * GlossaryHelp "?" button clarifying jargon used on that page's table
     * (Role, Policy, Permission, ...). Omit for a bare title. */
    titleExtra?: React.ReactNode;
    description?: string;
    /** Caps the description's width (a Tailwind max-w-* class) so a long
     * description wraps at that width instead of stretching to fill the
     * space next to `actions` - opt-in (default: full width) since most
     * pages have no `actions` card whose width needs protecting from a
     * wide first line of text. */
    descriptionMaxW?: string;
    /** Right-aligned slot next to the heading, typically a primary action
     * button or a summary/stats card. */
    actions?: React.ReactNode;
    /** Extra content rendered below the title/description, in the same
     * left-hand column, so it stacks beneath the title while staying in the
     * same header row as `actions`. Use this instead of `children` when
     * `actions` is tall (e.g. a stats card) and this content (a search
     * bar/filter row) should sit beside it, not below its full height. */
    headerExtra?: React.ReactNode;
    children: React.ReactNode;
}

/**
 * Consistent heading/description/action-slot layout for every management
 * page (Users, Policies, Audit Log, Account Settings) so they share one
 * page-header rhythm instead of each hand-rolling its own heading + flex.
 *
 * max-w-(--size-page-content) caps the width on wide monitors, left-aligned
 * next to the sidebar, so rows don't stretch until actions sit far from
 * their labels.
 */
const PageContainer: React.FC<PageContainerProps> = ({
    title,
    icon: Icon,
    titleExtra,
    breadcrumbs,
    description,
    descriptionMaxW,
    actions,
    headerExtra,
    children,
}) => {
    return (
        <div className="w-full max-w-(--size-page-content)">
            {breadcrumbs && breadcrumbs.length > 0 && <Breadcrumbs items={breadcrumbs} />}
            <div className="flex flex-col sm:flex-row justify-between items-start gap-5 mb-6">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2.5">
                        {Icon && <Icon size={22} aria-hidden="true" className="text-fg-muted" />}
                        {/* Same 22px/1.2/bold/-0.01em title style DashboardPage.tsx
                            hardcodes directly (it skips PageContainer for layout
                            reasons, not for a different title style) - kept
                            identical here so every page's h1 matches. */}
                        <h1 className="text-[24px] leading-[1.15] font-bold tracking-[-0.025em] text-fg-default">{title}</h1>
                        {titleExtra}
                    </div>
                    {description && (
                        <p className={cn("text-fg-muted text-[14.5px] leading-[1.4] mt-1", descriptionMaxW)}>{description}</p>
                    )}
                </div>
                {actions && <div>{actions}</div>}
            </div>
            {/* Full width of the page container, not squeezed into the
             * title's column - `actions` (e.g. UsersPage's Export CSV
             * button) sits beside the title/description above, so a stats
             * card here would otherwise be narrowed to leave room for it. */}
            {headerExtra && <div className="mb-6">{headerExtra}</div>}
            {children}
        </div>
    );
};

export default PageContainer;
