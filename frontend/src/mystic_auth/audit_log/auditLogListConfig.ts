/**
 * Pagination size, filter-placeholder value, timestamp formatting, and page-count/bool-filter
 * parsing shared by all four audit-log section components (authorization_log/ and
 * security_log/), kept here once instead of duplicated per tab.
 */

import { useMemo, useState } from "react";

import type { SupportedLanguage } from "../translations/translations";
import { formatNumber } from "../translations/numerals";
import { monthNameShort } from "../translations/monthNames";
import { formatHourMinute } from "../translations/timeOfDay";

export const PAGE_SIZE = 25;
export const ALL_VALUE = "";

/** e.g. "14 Aug 2026, 8:58 PM" - fixed dd-Mon-yyyy, not the browser's locale format (which
 * could read mm/dd/yyyy for a US viewer looking at the same row as someone elsewhere), so
 * every operator sees the same unambiguous format regardless of system locale. Month name,
 * digits, and time-of-day are still localized to the active language (see timeOfDay.ts for
 * hi/mr's native day-period words). */
export function formatTimestamp(iso: string, language: SupportedLanguage): string {
    const date = new Date(iso);
    const day = String(date.getDate()).padStart(2, "0");
    const month = monthNameShort(date.getMonth(), language);
    const year = date.getFullYear();
    const time = formatHourMinute(date, language);
    return formatNumber(`${day} ${month} ${year}, ${time}`, language);
}

export function totalPagesFor(total: number): number {
    return Math.max(1, Math.ceil(total / PAGE_SIZE));
}

/** "" (a placeholder "All" option) maps to `undefined` (no filter applied),
 * since the underlying value is never itself a legal filter value. */
export function toBoolFilter(value: string): boolean | undefined {
    if (value === ALL_VALUE) return undefined;
    return value === "true";
}

/** Preset day counts for the time-range picker (TimeRangeControl.tsx), matching the design's
 * Last 7/14/30/90-days rows and the backend login-trend endpoints' `days` (1-90) bound. */
export const TIME_RANGE_PRESETS = [7, 14, 30, 90] as const;
export type TimeRangePreset = (typeof TIME_RANGE_PRESETS)[number];
export type TimeRangeValue = `${TimeRangePreset}` | "custom";
export const DEFAULT_TIME_RANGE: TimeRangeValue = "14";

export interface TimeRangeState {
    range: TimeRangeValue;
    /** yyyy-mm-dd, only meaningful when range === "custom". */
    customFrom: string;
    customTo: string;
}

export const DEFAULT_TIME_RANGE_STATE: TimeRangeState = { range: DEFAULT_TIME_RANGE, customFrom: "", customTo: "" };

/** True once the range is off its 14-day default - drives the "active filter" chip/tint and
 * the Clear-filters count, same isActive contract every other filter in this page already
 * follows. A custom range with no dates picked yet (mid-edit) doesn't count as active. */
export function isTimeRangeActive(state: TimeRangeState): boolean {
    if (state.range === "custom") return !!state.customFrom && !!state.customTo;
    return state.range !== DEFAULT_TIME_RANGE;
}

function startOfDayIso(date: Date): string {
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    return d.toISOString();
}

function endOfDayIso(date: Date): string {
    const d = new Date(date);
    d.setHours(23, 59, 59, 999);
    return d.toISOString();
}

export interface TimeRangeApiParams {
    from: string | undefined;
    to: string | undefined;
    /** Day-count equivalent, for the two login-trend endpoints (`days` only, no from/to - see
     * .project/audit-log-design-review.md's backend section). For a custom range this is the
     * inclusive day span, clamped to the endpoint's [1, 90] bound. */
    days: number;
}

/**
 * Resolves the picked range into backend query params. `nowMs` is captured once per component
 * mount (see useTimeRangeParams below) rather than read fresh on every call: a preset's `to`
 * pinned to "the instant this render happened" would change the query's cache key (and refetch)
 * on every re-render, since a fresh Date.now() never string-matches the previous one.
 */
export function timeRangeToApiParams(state: TimeRangeState, nowMs: number): TimeRangeApiParams {
    if (state.range === "custom" && state.customFrom && state.customTo) {
        const from = new Date(`${state.customFrom}T00:00:00`);
        const to = new Date(`${state.customTo}T00:00:00`);
        const days = Math.max(1, Math.min(90, Math.round((to.getTime() - from.getTime()) / 86400000) + 1));
        return { from: startOfDayIso(from), to: endOfDayIso(to), days };
    }
    // "custom" with an incomplete pair of dates (e.g. mid-edit in TimeRangeControl, or a
    // hand-built state) has no day count of its own - falls back to the default preset rather
    // than Number("custom") (NaN) propagating into an invalid Date below.
    const days = Number(state.range === "custom" ? DEFAULT_TIME_RANGE : state.range);
    const to = new Date(nowMs);
    const from = new Date(nowMs - (days - 1) * 86400000);
    return { from: startOfDayIso(from), to: to.toISOString(), days };
}

/** "Last 14 days" / "2026-01-01 - 2026-01-07" - shared by TimeRangeControl's own trigger label
 * and each section's active-filter chip, so the two don't drift out of sync with each other. */
export function timeRangeLabel(state: TimeRangeState, t: (key: string, opts?: Record<string, unknown>) => string): string {
    if (state.range === "custom" && state.customFrom && state.customTo) {
        return state.customFrom === state.customTo
            ? state.customFrom
            : t("shared.timeRange.rangeText", { from: state.customFrom, to: state.customTo });
    }
    const preset = state.range === "custom" ? DEFAULT_TIME_RANGE : state.range;
    return t(`shared.timeRange.preset_${preset}`);
}

/** Memoized `{from, to, days}` for one range/customFrom/customTo triple, stable for this
 * component's lifetime (see timeRangeToApiParams's docstring on why `nowMs` can't be read
 * fresh on every render). */
export function useTimeRangeParams(state: TimeRangeState): TimeRangeApiParams {
    // Lazy useState initializer, not a ref: refs can't be read during render (React's rules of
    // hooks/purity lint), but a lazy initializer runs exactly once, on this component's first
    // render, which is exactly the "captured once at mount" semantics this needs.
    const [nowMs] = useState(() => Date.now());
    return useMemo(
        () => timeRangeToApiParams(state, nowMs),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [state.range, state.customFrom, state.customTo]
    );
}
