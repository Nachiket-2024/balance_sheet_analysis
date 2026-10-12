import React from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "../styles/classNames";

export interface FilterChip {
    key: string;
    label: React.ReactNode;
    onClear: () => void;
}

interface FilterChipsProps {
    chips: FilterChip[];
    onClearAll: () => void;
    className?: string;
}

/**
 * Active-filter chips (each individually clearable, brand-tinted) plus a
 * "Clear filters (N)" button when filters are active.
 */
const FilterChips: React.FC<FilterChipsProps> = ({ chips, onClearAll, className }) => {
    const { t } = useTranslation("audit_log");

    if (chips.length === 0) return null;

    return (
        <div className={cn("flex items-center gap-2 flex-wrap", className)}>
            {chips.map((chip) => (
                <span
                    key={chip.key}
                    className="flex items-center gap-1 rounded-full border border-[var(--brand-500)] bg-[var(--brand-200)] text-fg-default dark:border-[var(--brand-400)] dark:bg-[color-mix(in_srgb,var(--brand-solid)_30%,transparent)] pl-2.5 pr-1 py-0.5 text-xs font-medium"
                >
                    {chip.label}
                    <button
                        type="button"
                        onClick={chip.onClear}
                        aria-label={t("shared.clearFilters")}
                        className="flex items-center justify-center rounded-full p-0.5 hover:bg-[var(--brand-300)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_40%,transparent)]"
                    >
                        <X size={12} aria-hidden="true" />
                    </button>
                </span>
            ))}
            {chips.length > 0 && (
                <button
                    type="button"
                    onClick={onClearAll}
                    className="flex items-center gap-1.5 h-8 px-2.5 rounded-[var(--radius-control)] text-sm font-medium text-fg-muted border border-border-strong bg-bg-surface hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)] transition-colors"
                >
                    <X size={14} aria-hidden="true" />
                    {t("shared.clearFiltersCount", { count: chips.length })}
                </button>
            )}
        </div>
    );
};

export default FilterChips;
