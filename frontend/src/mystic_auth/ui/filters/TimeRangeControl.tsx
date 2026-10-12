import React, { useState } from "react";
import { CalendarRange, ChevronDown, X, Check } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Popover, PopoverContent, PopoverTrigger } from "../shadcn/popover";
import { Button } from "../buttons/Button";
import { cn } from "../styles/classNames";
import {
    TIME_RANGE_PRESETS,
    DEFAULT_TIME_RANGE,
    isTimeRangeActive,
    timeRangeLabel,
    type TimeRangeState,
    type TimeRangeValue,
} from "../../audit_log/auditLogListConfig";

interface TimeRangeControlProps {
    value: TimeRangeState;
    onChange: (next: TimeRangeState) => void;
    className?: string;
}

function todayIso(): string {
    return new Date().toISOString().slice(0, 10);
}

/**
 * "Time range" filter: Last 7/14/30/90-days presets as rows with a check, plus a custom From/To
 * range behind a hairline - design/audit-log.html's range popover. Same popover shape as
 * GroupedSearchSelect (a from-scratch trigger + Radix Popover, not StyledSelect, since this
 * needs two date inputs the plain single-select can't host).
 */
const TimeRangeControl: React.FC<TimeRangeControlProps> = ({ value, onChange, className }) => {
    const { t } = useTranslation("audit_log");
    const [open, setOpen] = useState(false);
    // Local draft for the custom-range inputs, applied only on "Apply custom range" - typing a
    // From date shouldn't refetch the table on every keystroke before a To date even exists.
    const [draftFrom, setDraftFrom] = useState(value.customFrom || todayIso());
    const [draftTo, setDraftTo] = useState(value.customTo || todayIso());

    const isActive = isTimeRangeActive(value);
    const today = todayIso();

    const rangeLabel = timeRangeLabel(value, t);

    const selectPreset = (preset: TimeRangeValue) => {
        onChange({ range: preset, customFrom: "", customTo: "" });
        setOpen(false);
    };

    const applyCustomRange = () => {
        onChange({ range: "custom", customFrom: draftFrom, customTo: draftTo });
        setOpen(false);
    };

    return (
        <Popover
            open={open}
            onOpenChange={(next) => {
                setOpen(next);
                if (next) {
                    setDraftFrom(value.customFrom || today);
                    setDraftTo(value.customTo || today);
                }
            }}
        >
            <div className={cn("flex items-center", isActive && "gap-1", className)}>
                <PopoverTrigger asChild>
                    <button
                        type="button"
                        aria-label={t("shared.timeRange.ariaLabel")}
                        className={cn(
                            "flex min-w-0 items-center gap-2 rounded-[var(--radius-control)] border h-9 px-3 text-sm overflow-hidden transition-colors outline-none focus-visible:border-brand-solid focus-visible:ring-[1px] focus-visible:ring-brand-solid cursor-pointer",
                            isActive
                                ? "border-[var(--brand-500)] bg-[var(--brand-200)] text-brand-fg hover:border-[var(--brand-600)] dark:border-[var(--brand-400)] dark:bg-[color-mix(in_srgb,var(--brand-solid)_30%,transparent)] dark:hover:border-[var(--brand-300)]"
                                : "border-border-strong bg-bg-surface text-fg-default hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)]"
                        )}
                    >
                        <CalendarRange size={16} className="shrink-0 opacity-70" aria-hidden="true" />
                        <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{rangeLabel}</span>
                        {!isActive && (
                            <ChevronDown size={16} className={cn("shrink-0 opacity-60 transition-transform", open && "rotate-180")} />
                        )}
                    </button>
                </PopoverTrigger>
                {isActive && (
                    <button
                        type="button"
                        aria-label={t("shared.timeRange.resetAriaLabel")}
                        onClick={() => onChange({ range: DEFAULT_TIME_RANGE, customFrom: "", customTo: "" })}
                        className="flex h-9 w-7 shrink-0 items-center justify-center rounded-[var(--radius-control)] border border-[var(--brand-500)] bg-[var(--brand-200)] text-brand-fg outline-none hover:bg-[var(--brand-300)] focus-visible:border-brand-solid focus-visible:ring-[1px] focus-visible:ring-brand-solid dark:border-[var(--brand-400)] dark:bg-[color-mix(in_srgb,var(--brand-solid)_30%,transparent)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_40%,transparent)]"
                    >
                        <X size={14} aria-hidden="true" />
                    </button>
                )}
            </div>
            <PopoverContent className="w-max min-w-[var(--radix-popover-trigger-width)] max-w-[min(28rem,calc(100vw-2rem))] p-0 overflow-hidden rounded-md border border-brand-border bg-popover text-popover-foreground shadow-md" align="start">
                <div className="dropdown-scroll-area max-h-56 overflow-y-auto p-1">
                    {TIME_RANGE_PRESETS.map((days) => {
                        const preset = `${days}` as TimeRangeValue;
                        const selected = value.range === preset;
                        return (
                            <button
                                key={preset}
                                type="button"
                                onClick={() => selectPreset(preset)}
                                className={cn(
                                    "flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-sm text-left cursor-pointer",
                                    selected
                                        ? "bg-[var(--brand-200)] text-brand-fg font-semibold shadow-[inset_0_0_0_1.5px_var(--brand-500)] hover:bg-brand-solid hover:text-brand-contrast hover:shadow-none dark:bg-brand-selected dark:shadow-[inset_0_0_0_1.5px_var(--brand-400)]"
                                        : "hover:bg-brand-selected"
                                )}
                            >
                                <span className="w-4 shrink-0">{selected && <Check size={14} className="text-brand-fg" aria-hidden="true" />}</span>
                                {t(`shared.timeRange.preset_${preset}` as const)}
                            </button>
                        );
                    })}
                </div>
                <div className="border-t border-border-default p-3 flex flex-col gap-2">
                    <div className="flex items-center gap-2">
                        <label className="flex-1 flex flex-col gap-1 text-xs text-fg-muted">
                            {t("shared.timeRange.from")}
                            <input
                                type="date"
                                value={draftFrom}
                                max={today}
                                onChange={(e) => setDraftFrom(e.target.value)}
                                className="rounded-[var(--radius-control)] border border-border-strong bg-bg-surface px-2 py-1 text-sm text-fg-default outline-none focus-visible:border-brand-solid"
                            />
                        </label>
                        <label className="flex-1 flex flex-col gap-1 text-xs text-fg-muted">
                            {t("shared.timeRange.to")}
                            <input
                                type="date"
                                value={draftTo}
                                max={today}
                                onChange={(e) => setDraftTo(e.target.value)}
                                className="rounded-[var(--radius-control)] border border-border-strong bg-bg-surface px-2 py-1 text-sm text-fg-default outline-none focus-visible:border-brand-solid"
                            />
                        </label>
                    </div>
                    <Button
                        type="button"
                        size="sm"
                        className="self-end"
                        disabled={!draftFrom || !draftTo || draftFrom > draftTo}
                        onClick={applyCustomRange}
                    >
                        {t("shared.timeRange.applyCustomRange")}
                    </Button>
                </div>
            </PopoverContent>
        </Popover>
    );
};

export default TimeRangeControl;
