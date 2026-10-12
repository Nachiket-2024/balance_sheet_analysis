import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "../styles/classNames";

interface CollapsibleSectionProps {
    title: string;
    children: React.ReactNode;
    /** Render as an always-open detail section without a disclosure control. */
    staticOpen?: boolean;
    /** Controlled open state, so a "Collapse all"/"Expand all" pair above several sections can
     * drive them together - omit for an independently-toggled section (uncontrolled, starts
     * open). */
    isOpen?: boolean;
    onToggle?: () => void;
}

/**
 * One card section within DetailsDrawer (Decision, Policies, Request context, ...): a header
 * button toggling a body, styled as its own bordered card with a gap from its neighbors
 * (design/audit-log.html's "Sections are separate cards with gaps"). Plain div-based expand/
 * collapse rather than Radix's Accordion/Collapsible - each section here is independent (any
 * combination can be open at once), which Accordion's single/multi "item" model adds ceremony
 * for without buying anything a plain boolean doesn't already give.
 */
const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({ title, children, staticOpen = false, isOpen: controlledOpen, onToggle }) => {
    const [uncontrolledOpen, setUncontrolledOpen] = useState(true);
    const isOpen = controlledOpen ?? uncontrolledOpen;
    const toggle = onToggle ?? (() => setUncontrolledOpen((v) => !v));

    return (
        <div className="border border-border-default rounded-lg bg-bg-surface">
            {staticOpen ? (
                <div className="px-4 pt-3 text-sm font-semibold">{title}</div>
            ) : (
                <button
                    type="button"
                    onClick={toggle}
                    aria-expanded={isOpen}
                    className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-semibold cursor-pointer hover:bg-row-hover"
                >
                    {title}
                    <ChevronDown size={16} className={cn("shrink-0 transition-transform", isOpen && "rotate-180")} aria-hidden="true" />
                </button>
            )}
            {(staticOpen || isOpen) && <div className="px-4 pb-4 pt-2 text-sm [overflow-wrap:anywhere]">{children}</div>}
        </div>
    );
};

export default CollapsibleSection;
