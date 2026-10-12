import React, { useRef } from "react";

import { cn } from "../styles/classNames";

export interface SegmentedControlOption {
    value: string;
    label: React.ReactNode;
    /** Small colored dot before the label (e.g. green for "Allowed", red for "Denied") -
     * design/audit-log.html's Result segmented control. Omit for a plain text option. */
    dotClassName?: string;
}

interface SegmentedControlProps {
    value: string;
    onChange: (value: string) => void;
    options: SegmentedControlOption[];
    ariaLabel: string;
    /** True when `value` is off the group's own default option, same isActive contract as
     * StyledSelect/GroupedSearchSelect - tints the whole control so a set filter reads as set
     * at a glance. */
    isActive?: boolean;
    className?: string;
    /** Use the same roving-focus tab semantics as UserAccessDialog when the
     * control switches visible dialog panels rather than filtering data. */
    tabRole?: boolean;
    tabPanelIds?: string[];
}

/**
 * One-click segmented control (a row of toggle buttons, exactly one pressed at a time), for a
 * small fixed vocabulary that would otherwise be an open-then-pick StyledSelect - Result
 * (Allowed/Denied, Success/Failed) here, and the login chart's All/Failed-only and Chart/Table
 * toggles. See .project/audit-log-design-review.md's "Result as a one-click segmented control".
 */
const SegmentedControl: React.FC<SegmentedControlProps> = ({ value, onChange, options, ariaLabel, className, tabRole = false, tabPanelIds }) => {
    const buttonRefs = useRef<Array<HTMLButtonElement | null>>([]);
    const activateByKeyboard = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
        const nextIndex =
            event.key === "ArrowRight" || event.key === "ArrowDown" ? (index + 1) % options.length :
                event.key === "ArrowLeft" || event.key === "ArrowUp" ? (index + options.length - 1) % options.length :
                    event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : index;
        if (nextIndex !== index) {
            event.preventDefault();
            onChange(options[nextIndex].value);
            requestAnimationFrame(() => buttonRefs.current[nextIndex]?.focus());
        }
    };

    return (
        <div
            role={tabRole ? "tablist" : "group"}
            aria-label={ariaLabel}
            className={cn(
                "inline-flex items-center gap-0 overflow-hidden rounded-lg border border-border-strong bg-bg-surface",
                className
            )}
        >
            {options.map((option, index) => {
                const pressed = option.value === value;
                return (
                    <button
                        key={option.value}
                        ref={(element) => { buttonRefs.current[index] = element; }}
                        id={tabRole && tabPanelIds?.[index] ? tabPanelIds[index].replace("tabpanel-", "tab-") : undefined}
                        type="button"
                        {...(tabRole
                            ? {
                                role: "tab" as const,
                                "aria-selected": pressed,
                                "aria-controls": tabPanelIds?.[index],
                                tabIndex: pressed ? 0 : -1,
                            }
                            : { "aria-pressed": pressed })}
                        onClick={() => onChange(option.value)}
                        onKeyDown={(event) => activateByKeyboard(event, index)}
                        className={cn(
                            "flex items-center gap-1.5 px-3 py-2 text-sm font-semibold transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] outline-none focus-visible:ring-[1px] focus-visible:ring-brand-solid whitespace-nowrap",
                            index !== 0 && "border-l border-border-strong",
                            pressed
                                ? "bg-brand-tile-subtle text-brand-fg shadow-[inset_0_0_0_2px_var(--brand-solid)]"
                                : "text-fg-muted hover:text-brand-fg hover:bg-brand-subtle"
                        )}
                    >
                        {option.dotClassName && <span className={cn("size-2 rounded-full shrink-0", option.dotClassName)} aria-hidden="true" />}
                        {option.label}
                    </button>
                );
            })}
        </div>
    );
};

export default SegmentedControl;
