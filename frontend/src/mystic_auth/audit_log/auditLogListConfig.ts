/**
 * The pagination size, filter-placeholder value, timestamp formatting, and
 * page-count/bool-filter parsing every audit-log list table needs to render
 * itself consistently: all four section components, in both
 * authorization_log/ and security_log/, depend on these same five things
 * identically, so this is the one place they live rather than each tab
 * duplicating them.
 */

import type { SupportedLanguage } from "../translations/translations";
import { formatNumber } from "../translations/numerals";
import { monthNameShort } from "../translations/monthNames";
import { formatHourMinute } from "../translations/timeOfDay";

export const PAGE_SIZE = 25;
export const ALL_VALUE = "";

/** e.g. "14 Aug 2026, 8:58 PM" - fixed dd-Mon-yyyy (not the browser's locale
 * format, which could read mm/dd/yyyy for a US-locale viewer looking at the
 * same log row as a viewer elsewhere), so a timestamp reads unambiguously
 * the same way for every operator regardless of their system locale, with
 * the month name, digits, and time-of-day all localized to the active
 * language (see timeOfDay.ts for hi/mr's native day-period words). */
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
