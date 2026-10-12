import React from "react";
import { Select as SelectPrimitive } from "radix-ui";
import { Check, ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";

import AppTooltip from "../feedback/AppTooltip";
import { cn } from "../styles/classNames";

export interface StyledSelectOption {
    label: string;
    value: string;
}

interface StyledSelectProps {
    value: string;
    onChange: (value: string) => void;
    options: StyledSelectOption[];
    ariaLabel: string;
    size?: "sm" | "md";
    className?: string;
    textTransform?: "capitalize";
    disabled?: boolean;
    title?: string;
    /** Text shown in the trigger when `value` matches no option, for a
     * caller that needs a genuine "nothing chosen yet" state rather than
     * "one option IS the empty/all state." Omit for that existing pattern. */
    placeholder?: string;
    /** True while the caller's options are still being fetched (e.g. a
     * server-backed filter list). Disables the trigger and swaps in a
     * "Loading..." placeholder instead of rendering a briefly-empty list. */
    isLoading?: boolean;
    /** True when `value` is off the filter bar's own "All"/default option -
     * design/users.html's `.fsel.is-set`. The caller (not this component)
     * knows what its own default value is, so it passes the comparison
     * result rather than this component guessing from `value` alone. Adds a
     * brand tint/border so a set filter is visible at a glance instead of
     * reading identical to every other unfiltered select on the page. */
    isActive?: boolean;
}

// Radix's <Select.Item> rejects a value of "" outright (it's reserved
// internally to mean "no selection" / show the placeholder) - but this app's
// filter bars routinely use "" as a real, selectable "All" option value
// (ALL_VALUE across every *FilterBar.tsx). This sentinel stands in for ""
// at the Radix boundary only; onChange/value still deal in the caller's
// real "" everywhere else.
const EMPTY_VALUE_SENTINEL = "__styled_select_empty__";
const toRadixValue = (value: string) => (value === "" ? EMPTY_VALUE_SENTINEL : value);
const fromRadixValue = (value: string) => (value === EMPTY_VALUE_SENTINEL ? "" : value);

/**
 * Filter/inline-picker dropdown shared by every select-shaped control in the
 * app. Wraps Radix's `Select` (ui/shadcn/select.tsx's primitives inlined
 * here rather than reused as-is, since this needs the isActive tint and the
 * "" sentinel mapping shadcn's generated primitive doesn't have reason to
 * know about).
 */
const StyledSelect: React.FC<StyledSelectProps> = ({
    value, onChange, options, ariaLabel, size = "md", className, textTransform, disabled, title, placeholder, isLoading, isActive,
}) => {
    const { t } = useTranslation("ui_text");
    // Radix only falls back to the placeholder slot when its own `value` is
    // exactly "" (shouldShowPlaceholder in @radix-ui/react-select) - not
    // merely "matches no option", so a real, non-empty `value` with no
    // matching option (or `isLoading`, which should always show the loading
    // placeholder regardless of the last real value) needs "" forced through
    // to Radix specifically to get that fallback.
    const hasMatch = options.some((o) => o.value === value);
    const radixValue = isLoading || !hasMatch ? "" : toRadixValue(value);

    return (
        <AppTooltip content={title}>
            <SelectPrimitive.Root
                // Remounts once real options first arrive (server-backed
                // filter lists start at options=[] while loading). Radix's
                // internal hidden bubble-input syncs its native <select>'s
                // value in an effect that runs against whatever options are
                // registered at that instant - if `value` arrives correctly
                // set (e.g. from a policy being edited) but the matching
                // <Item>/<option> hasn't registered yet because options
                // populated one render later, the browser's native select
                // finds no matching <option>, silently resets to "", and
                // Radix reads that back as a real onValueChange(""), wiping
                // out the caller's value. Keying on whether options exist
                // yet forces a fresh mount once they do, so the bubble
                // input's native options are correct from its very first
                // render instead of racing a stale, empty set.
                key={options.length > 0 ? "loaded" : "loading"}
                value={radixValue}
                onValueChange={(next) => onChange(fromRadixValue(next))}
                disabled={disabled || isLoading}
            >
                {/* Real native <select>, kept in sync and aria-hidden - not
                    for styling, purely so this control still has a
                    standard hidden-select fallback (form autofill, and
                    what this app's test suite drives via
                    userEvent.selectOptions instead of simulating
                    Radix's pointer-based listbox, which jsdom doesn't
                    support well). */}
                <select
                    aria-label={ariaLabel}
                    aria-hidden="true"
                    tabIndex={-1}
                    className="sr-only"
                    value={value}
                    disabled={disabled || isLoading}
                    onChange={(e) => onChange(e.target.value)}
                >
                    {options.map((option) => (
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    ))}
                </select>
                <SelectPrimitive.Trigger
                    aria-label={ariaLabel}
                    className={cn(
                        // Same brand-tinted chip look as every other icon/filter
                        // control (design/dashboard.html's .search-box/.icon-btn):
                        // border-strong at rest, a brand-tinted hover instead of a
                        // plain gray one.
                        "flex items-center justify-between gap-2 rounded-[var(--radius-control)] border h-9 px-3 text-sm overflow-hidden transition-colors outline-none disabled:pointer-events-none disabled:opacity-50 focus-visible:border-brand-solid focus-visible:ring-[1px] focus-visible:ring-brand-solid",
                        size === "sm" ? "h-8 text-sm" : "h-9",
                        textTransform === "capitalize" && "capitalize",
                        isActive
                            ? "border-[var(--brand-500)] bg-[var(--brand-200)] text-brand-fg hover:border-[var(--brand-600)] dark:border-[var(--brand-400)] dark:bg-[color-mix(in_srgb,var(--brand-solid)_30%,transparent)] dark:hover:border-[var(--brand-300)]"
                            : "border-border-strong bg-bg-surface text-fg-default hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)]",
                        className
                    )}
                >
                    {/* Wrapper span, not className on Value itself: Radix's
                        SelectValue destructures `className` (and `style`)
                        out of its props and never applies either to the
                        span it renders (@radix-ui/react-select's
                        SelectValue2), so a long unselected label never
                        actually got truncated with an ellipsis before. */}
                    <span className="overflow-hidden text-ellipsis whitespace-nowrap">
                        <SelectPrimitive.Value placeholder={isLoading ? t("loading") : placeholder} />
                    </span>
                    <SelectPrimitive.Icon asChild>
                        <ChevronDown
                            size={16}
                            className="shrink-0 opacity-60 transition-transform data-[state=open]:rotate-180"
                        />
                    </SelectPrimitive.Icon>
                </SelectPrimitive.Trigger>
                <SelectPrimitive.Portal>
                    <SelectPrimitive.Content
                        position="popper"
                        sideOffset={4}
                        // Fade-only motion keeps Radix's popper transform free for positioning.
                        // max-h is capped by Radix's own --radix-select-content-available-height
                        // (not just a flat max-h-80): without it, a trigger opened near the
                        // bottom of the viewport lets the content render taller than the space
                        // actually available, so the tail of a long option list renders past the
                        // viewport edge - invisible and unreachable by scrolling, not just
                        // "unscrolled". No Scroll{Up,Down}Button pair - those render as
                        // extra chevron affordances inside the list, which this app doesn't
                        // use anywhere else (GroupedSearchSelect's plain-div list scrolls
                        // with no buttons either); a bounded viewport's native overflow is
                        // enough on its own.
                        className="z-[1500] w-max min-w-[var(--radix-select-trigger-width)] max-w-[min(28rem,calc(100vw-2rem))] overflow-hidden rounded-md border border-brand-border bg-popover p-0 text-popover-foreground shadow-md data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
                    >
                        <SelectPrimitive.Viewport className="dropdown-scroll-area max-h-[min(20rem,var(--radix-select-content-available-height))] overflow-y-auto p-1 min-w-[var(--radix-select-trigger-width)]">
                            {options.map((option) => (
                                <SelectPrimitive.Item
                                    key={option.value}
                                    value={toRadixValue(option.value)}
                                    className={cn(
                                        "flex w-full cursor-pointer select-none items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-sm text-left outline-none",
                                        // Three distinct states: plain at rest, solid
                                        // brand fill on hover/keyboard-focus, tinted
                                        // wash + border + checkmark for the selection
                                        // (a background tint alone reads as merged into
                                        // the popover surface, especially in dark mode).
                                        "data-[highlighted]:bg-brand-solid data-[highlighted]:text-brand-contrast",
                                        "data-[state=checked]:bg-[var(--brand-200)] data-[state=checked]:text-brand-fg data-[state=checked]:font-semibold data-[state=checked]:shadow-[inset_0_0_0_1.5px_var(--brand-500)] dark:data-[state=checked]:bg-brand-selected dark:data-[state=checked]:shadow-[inset_0_0_0_1.5px_var(--brand-400)] data-[state=checked]:data-[highlighted]:bg-brand-solid data-[state=checked]:data-[highlighted]:text-brand-contrast data-[state=checked]:data-[highlighted]:shadow-none",
                                        textTransform === "capitalize" && "capitalize"
                                    )}
                                >
                                    {/* A real flex child, not `absolute` - `absolute`
                                        left the label with no reserved space for it, so
                                        a label that ran close to the trigger's width (e.g.
                                        "All roles" in a narrow select) overlapped the
                                        checkmark instead of yielding space to it. Only
                                        renders at all for the checked item, so this only
                                        costs layout width on that one row. */}
                                    <SelectPrimitive.ItemText className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
                                        {option.label}
                                    </SelectPrimitive.ItemText>
                                    <SelectPrimitive.ItemIndicator className="inline-flex shrink-0 items-center">
                                        <Check size={14} aria-hidden="true" />
                                    </SelectPrimitive.ItemIndicator>
                                </SelectPrimitive.Item>
                            ))}
                        </SelectPrimitive.Viewport>
                    </SelectPrimitive.Content>
                </SelectPrimitive.Portal>
            </SelectPrimitive.Root>
        </AppTooltip>
    );
};

export default StyledSelect;
