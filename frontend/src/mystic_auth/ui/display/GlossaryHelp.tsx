import { CircleHelp } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "../shadcn/popover";

export interface GlossaryItem {
    term: string;
    definition: string;
}

interface GlossaryHelpProps {
    items: GlossaryItem[];
    /** Read out by screen readers on the trigger button - say what the
     * popover explains (e.g. "What do Role, Policy and Permission mean?"),
     * not just "Help", since that's the only label the button ever gets. */
    ariaLabel: string;
}

/**
 * Small "?" button next to a page's title that opens a plain-language
 * lookup for jargon used in that page's table (Role, Policy, Permission,
 * Verified, ...) - one click away and otherwise out of the way, not a
 * legend someone has to read before the page makes sense
 * (design/users.html's help-wrap/help-pop).
 */
export default function GlossaryHelp({ items, ariaLabel }: GlossaryHelpProps) {
    return (
        <Popover>
            <PopoverTrigger asChild>
                <button
                    type="button"
                    aria-label={ariaLabel}
                    title={ariaLabel}
                    className="flex size-[26px] shrink-0 items-center justify-center rounded-full border border-border text-fg-muted transition-colors hover:border-brand-border hover:bg-brand-subtle hover:text-brand-fg"
                >
                    <CircleHelp size={15} aria-hidden="true" />
                </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-80 p-4">
                <dl className="flex flex-col divide-y divide-border">
                    {items.map(({ term, definition }) => (
                        <div key={term} className="py-2 first:pt-0 last:pb-0">
                            <dt className="text-[13.5px] font-semibold text-fg-default">{term}</dt>
                            <dd className="mt-0.5 text-sm leading-snug text-fg-muted">{definition}</dd>
                        </div>
                    ))}
                </dl>
            </PopoverContent>
        </Popover>
    );
}
