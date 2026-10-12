import React from "react";

import { cn } from "../styles/classNames";

export interface QuickFilterOption {
    value: string;
    label: React.ReactNode;
    count: number | string;
    danger?: boolean;
    disabled?: boolean;
}

interface QuickFilterSegmentProps {
    value: string;
    options: QuickFilterOption[];
    ariaLabel: string;
    onChange: (value: string) => void;
    disabled?: boolean;
    className?: string;
}

const QuickFilterSegment: React.FC<QuickFilterSegmentProps> = ({
    value,
    options,
    ariaLabel,
    onChange,
    disabled = false,
    className,
}) => {
    return (
        <div
            className={cn(
                "flex items-center gap-0 border border-border-strong rounded-lg bg-bg-surface overflow-hidden",
                disabled ? "opacity-50 pointer-events-none" : "opacity-100 pointer-events-auto",
                className
            )}
            role="radiogroup"
            aria-label={ariaLabel}
        >
            {options.map((option, i) => {
                const on = value === option.value;
                return (
                    <button
                        type="button"
                        key={option.value}
                        role="radio"
                        aria-checked={on}
                        disabled={disabled || option.disabled}
                        onClick={() => onChange(option.value)}
                        className={cn(
                            "px-3 py-2 text-sm font-semibold cursor-pointer flex items-center gap-2 whitespace-nowrap transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)]",
                            i !== 0 && "border-l border-border-strong",
                            on
                                ? option.danger
                                    ? "text-red-fg bg-red-subtle shadow-[inset_0_0_0_2px_var(--red-600)]"
                                    : "text-brand-fg bg-brand-tile-subtle shadow-[inset_0_0_0_2px_var(--brand-solid)]"
                                : option.danger
                                  ? "text-fg-muted bg-transparent hover:bg-red-subtle hover:text-red-fg"
                                  : "text-fg-muted bg-transparent hover:bg-brand-subtle hover:text-brand-fg"
                        )}
                    >
                        {option.label}
                        <span
                            className={cn(
                                "text-xs rounded-full px-1.5 min-w-5 text-center",
                                on
                                    ? option.danger
                                        ? "text-white bg-[var(--red-600)]"
                                        : "text-white bg-brand-solid"
                                    : "text-fg-muted bg-bg-muted"
                            )}
                        >
                            {option.count}
                        </span>
                    </button>
                );
            })}
        </div>
    );
};

export default QuickFilterSegment;
