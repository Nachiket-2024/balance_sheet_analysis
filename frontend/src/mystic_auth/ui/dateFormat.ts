import type { SupportedLanguage } from "../translations/translations";
import { formatNumber } from "../translations/numerals";
import { monthNameShort } from "../translations/monthNames";
import { formatHourMinute } from "../translations/timeOfDay";

/**
 * Generic date/time formatting, no feature ownership: shared by DashboardPage
 * (member-since, last-login), ManageSessionsCard/UserDetailsDialog
 * (signed-in/last-seen/created columns), and any future feature that needs
 * the same fixed "dd Mon yyyy" display - day-before-month (not
 * toLocaleDateString's en-US month-first ordering) so a date reads
 * unambiguously the same way regardless of viewer locale, with the month
 * name, digits, and time-of-day (see timeOfDay.ts - hi/mr use native
 * day-period words, not a literal "AM"/"PM") all localized to the active
 * language.
 */

function pad2(n: number): string {
    return String(n).padStart(2, "0");
}

/** e.g. "15 Jan 2026". */
export function formatMemberSince(iso: string, language: SupportedLanguage): string {
    const date = new Date(iso);
    const formatted = `${pad2(date.getDate())} ${monthNameShort(date.getMonth(), language)} ${date.getFullYear()}`;
    return formatNumber(formatted, language);
}

/** e.g. "25 Jul 2026, 8:58 PM" - full date, year, and time together: a
 * relative "2h ago" reads fine for a login just now, but is ambiguous for a
 * login weeks old and useless for comparing several sessions against each
 * other - an actual timestamp always answers "when, exactly". */
export function formatDateTime(iso: string, language: SupportedLanguage): string {
    const date = new Date(iso);
    const time = formatHourMinute(date, language);
    const formatted = `${pad2(date.getDate())} ${monthNameShort(date.getMonth(), language)} ${date.getFullYear()}, ${time}`;
    return formatNumber(formatted, language);
}

/** e.g. "4:23 PM" - the time-only half of formatDateTime, for the
 * Dashboard's "Last login" stat: that stat sits in a narrow fixed-width
 * column next to two much shorter stats, so the full "1 Aug 2026, 4:23 PM"
 * string is split across two lines (date via formatMemberSince above, time
 * via this) instead of forcing the column wide enough for one long line. */
export function formatTimeOnly(iso: string, language: SupportedLanguage): string {
    return formatHourMinute(new Date(iso), language);
}
