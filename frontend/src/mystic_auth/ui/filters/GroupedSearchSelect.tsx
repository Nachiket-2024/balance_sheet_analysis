import React, { useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Popover, PopoverContent, PopoverTrigger } from "../shadcn/popover";
import { cn } from "../styles/classNames";

export interface GroupedSearchOption {
    value: string;
    /** Shown as the main line. */
    label: string;
    /** Shown as a smaller line under `label` (e.g. the raw event/action code
     * when `label` is a friendlier translated name). Omit when label alone
     * is already the canonical form. */
    sublabel?: string;
    /** Result count for the current filters, shown right-aligned. Omit to
     * hide the count entirely (no facets endpoint available). */
    count?: number;
    /** Renders a small warning icon next to the option (e.g. a destructive
     * action), same idea as PolicyCard's destructive-count marker. */
    destructive?: boolean;
}

export interface GroupedSearchOptionGroup {
    key: string;
    label: string;
    options: GroupedSearchOption[];
}

interface GroupedSearchSelectProps {
    value: string;
    onChange: (value: string) => void;
    groups: GroupedSearchOptionGroup[];
    /** Value/label for the always-present "All ..." option at the top. */
    allValue: string;
    allLabel: string;
    ariaLabel: string;
    searchPlaceholder: string;
    /** True when `value` is off the default "All" option - same isActive
     * contract as StyledSelect, tints the trigger so a set filter is
     * visible at a glance. */
    isActive: boolean;
    className?: string;
    /**
     * Selecting a whole group (clicking its sticky header) narrows to every
     * option in that group at once - e.g. the Action picker's resource-type
     * group header sets the Resource filter instead of a single action.
     * Omit for a picker with no such "select the whole group" affordance.
     */
    onSelectGroup?: (groupKey: string) => void;
}

/**
 * Searchable, grouped single-select combobox: a typed query narrows visible
 * options across every group at once, sticky group headers stay visible
 * while scrolling a long list, and arrow keys move a highlighted row
 * independent of literal DOM/mouse focus (Radix's own Select has no search
 * box and no grouping, hence this from-scratch popover instead of
 * StyledSelect - see .project/audit-log-design-review.md's "Picks needed"
 * for the shared-with-Users-page context this was built under).
 *
 * Deliberately generic over `groups`/`allValue`/`allLabel` rather than
 * baking in "actions" or "events": both the Action and Event pickers on
 * this page, and any future page needing the same shape, pass their own
 * vocabulary in.
 */
const GroupedSearchSelect: React.FC<GroupedSearchSelectProps> = ({
    value, onChange, groups, allValue, allLabel, ariaLabel, searchPlaceholder, isActive, className, onSelectGroup,
}) => {
    const { t } = useTranslation("ui_text");
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    // -1 means no option is visually highlighted on open. Starting at zero
    // made the first option look hovered before the caller had moved over it.
    // ArrowDown still enters the list at the first option.
    const [highlighted, setHighlighted] = useState(-1);
    const inputRef = useRef<HTMLInputElement>(null);

    const selectedOption = useMemo(
        () => groups.flatMap((g) => g.options).find((o) => o.value === value),
        [groups, value]
    );
    const triggerLabel = value === allValue || !selectedOption ? allLabel : selectedOption.label;

    const normalizedQuery = query.trim().toLowerCase();
    const filteredGroups = useMemo(() => {
        if (!normalizedQuery) return groups;
        return groups
            .map((g) => ({
                ...g,
                options: g.options.filter(
                    (o) =>
                        o.label.toLowerCase().includes(normalizedQuery) ||
                        o.value.toLowerCase().includes(normalizedQuery) ||
                        o.sublabel?.toLowerCase().includes(normalizedQuery)
                ),
            }))
            .filter((g) => g.options.length > 0);
    }, [groups, normalizedQuery]);

    // Flattened so arrow-key navigation can move through every visible option
    // (across group boundaries) with one running index, regardless of how
    // they're visually nested under sticky headers.
    const flatOptions = useMemo(() => filteredGroups.flatMap((g) => g.options), [filteredGroups]);

    const selectAndClose = (next: string) => {
        onChange(next);
        setOpen(false);
        setQuery("");
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setHighlighted((i) => Math.min(i + 1, flatOptions.length - 1));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlighted((i) => Math.max(i - 1, 0));
        } else if (e.key === "Enter") {
            e.preventDefault();
            const option = flatOptions[highlighted];
            if (option) selectAndClose(option.value);
        } else if (e.key === "Escape") {
            setOpen(false);
        }
    };

    return (
        <Popover
            open={open}
            onOpenChange={(next) => {
                setOpen(next);
                setQuery("");
            setHighlighted(-1);
                // Popover.Content isn't in the DOM the instant `open` flips true
                // (Radix mounts it on its own next tick), so a synchronous
                // .focus() here would target nothing; queue it for right after.
                if (next) setTimeout(() => inputRef.current?.focus(), 0);
            }}
        >
            <PopoverTrigger asChild>
                <button
                    type="button"
                    aria-label={ariaLabel}
                    className={cn(
                        "flex items-center justify-between gap-2 rounded-[var(--radius-control)] border h-9 px-3 text-sm overflow-hidden transition-colors outline-none focus-visible:border-brand-solid focus-visible:ring-[1px] focus-visible:ring-brand-solid cursor-pointer",
                        isActive
                            ? "border-[var(--brand-500)] bg-[var(--brand-200)] text-brand-fg hover:border-[var(--brand-600)] dark:border-[var(--brand-400)] dark:bg-[color-mix(in_srgb,var(--brand-solid)_30%,transparent)] dark:hover:border-[var(--brand-300)]"
                            : "border-border-strong bg-bg-surface text-fg-default hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)]",
                        className
                    )}
                >
                    <span className="overflow-hidden text-ellipsis whitespace-nowrap">{triggerLabel}</span>
                    <ChevronDown size={16} className={cn("shrink-0 opacity-60 transition-transform", open && "rotate-180")} />
                </button>
            </PopoverTrigger>
            <PopoverContent
                className="w-max min-w-[var(--radix-popover-trigger-width)] max-w-[min(28rem,calc(100vw-2rem))] p-0 overflow-hidden rounded-md border border-brand-border bg-popover text-popover-foreground shadow-md"
                align="start"
                onOpenAutoFocus={(e) => e.preventDefault()}
            >
                <div className="flex items-center gap-2 border-b border-border-default px-3 py-2">
                    <Search size={14} className="text-fg-muted shrink-0" aria-hidden="true" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => {
                            setQuery(e.target.value);
                setHighlighted(-1);
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder={searchPlaceholder}
                        aria-label={searchPlaceholder}
                        className="flex-1 bg-transparent text-sm outline-none placeholder:text-fg-muted"
                    />
                </div>

                <div className="dropdown-scroll-area max-h-80 overflow-y-auto p-1">
                    <button
                        type="button"
                        onClick={() => selectAndClose(allValue)}
                        className={cn(
                            "flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-sm text-left cursor-pointer",
                            value === allValue
                                ? "bg-[var(--brand-200)] text-brand-fg font-semibold shadow-[inset_0_0_0_1.5px_var(--brand-500)] hover:bg-brand-solid hover:text-brand-contrast hover:shadow-none dark:bg-brand-selected dark:shadow-[inset_0_0_0_1.5px_var(--brand-400)]"
                                : "hover:bg-brand-selected"
                        )}
                    >
                        {allLabel}
                        {value === allValue && <Check size={14} className="text-brand-fg" aria-hidden="true" />}
                    </button>

                    {filteredGroups.length === 0 && (
                        <p className="px-2 py-3 text-sm text-fg-muted text-center">{t("noMatches")}</p>
                    )}

                    {filteredGroups.map((group) => (
                        <div key={group.key}>
                            {/* sticky, not just a plain header: this list can run to dozens of
                                options, and a scrolled-past group name is exactly the context a
                                long list needs to stay orientable. */}
                            <button
                                type="button"
                                onClick={() => {
                                    onSelectGroup?.(group.key);
                                    setOpen(false);
                                    setQuery("");
                                }}
                                disabled={!onSelectGroup}
                                className={cn(
                                    "sticky -mt-1 top-[-5px] z-10 w-full text-left bg-popover px-2 py-1 text-xs font-semibold text-fg-muted uppercase tracking-wide",
                                    onSelectGroup && "cursor-pointer hover:text-brand-fg"
                                )}
                            >
                                {group.label}
                            </button>
                            {group.options.map((option) => {
                                const flatIndex = flatOptions.indexOf(option);
                                const isHighlighted = flatIndex === highlighted;
                                return (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onMouseEnter={() => setHighlighted(flatIndex)}
                                        onClick={() => selectAndClose(option.value)}
                                        className={cn(
                                            "flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-sm text-left cursor-pointer",
                                            isHighlighted
                                                ? "bg-brand-solid text-brand-contrast"
                                                : option.value === value
                                                  ? "bg-[var(--brand-200)] text-brand-fg font-semibold shadow-[inset_0_0_0_1.5px_var(--brand-500)] hover:bg-brand-solid hover:text-brand-contrast hover:shadow-none dark:bg-brand-selected dark:shadow-[inset_0_0_0_1.5px_var(--brand-400)]"
                                                  : "hover:bg-brand-selected"
                                        )}
                                    >
                                        <span className="flex flex-col min-w-0">
                                            <span className="flex items-center gap-1.5 truncate">
                                                {option.label}
                                                {option.destructive && (
                                                    <span className="text-red-fg shrink-0" aria-hidden="true">⚠</span>
                                                )}
                                            </span>
                                            {option.sublabel && (
                                                <span className="text-xs text-fg-muted truncate">{option.sublabel}</span>
                                            )}
                                        </span>
                                        <span className="flex items-center gap-1.5 shrink-0">
                                            {option.count !== undefined && (
                                                <span className="text-xs text-fg-muted">{option.count}</span>
                                            )}
                                            {option.value === value && <Check size={14} className="text-brand-fg" aria-hidden="true" />}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    ))}
                </div>
            </PopoverContent>
        </Popover>
    );
};

export default GroupedSearchSelect;
