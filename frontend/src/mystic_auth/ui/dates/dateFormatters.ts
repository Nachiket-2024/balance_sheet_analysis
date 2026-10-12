import type { SupportedLanguage } from "../../translations/translations";
import { formatNumber } from "../../translations/numerals";
import { monthNameShort } from "../../translations/monthNames";
import { formatHourMinute } from "../../translations/timeOfDay";

/**
 * Generic date/time formatting, shared by DashboardPage (member-since,
 * last-login), ActiveSessionsCard/UserDetailsDialog (signed-in/last-seen/
 * created columns), and any future feature needing a fixed "dd Mon yyyy"
 * display: day-before-month (not toLocaleDateString's en-US month-first
 * order) so a date reads unambiguously regardless of viewer locale, with
 * month name, digits, and time-of-day (timeOfDay.ts: hi/mr use native
 * day-period words, not a literal "AM"/"PM") localized to the active language.
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

/** e.g. "25 Jul 2026, 8:58 PM" - full date, year, and time together. The
 * default for timestamps: a relative "2h ago" alone is ambiguous for
 * something weeks old. Where a relative time is shown (formatRelativeTime),
 * pair it with this for the exact value. */
export function formatDateTime(iso: string, language: SupportedLanguage): string {
    const date = new Date(iso);
    const time = formatHourMinute(date, language);
    const formatted = `${pad2(date.getDate())} ${monthNameShort(date.getMonth(), language)} ${date.getFullYear()}, ${time}`;
    return formatNumber(formatted, language);
}

/** e.g. "4:23 PM" - the time-only half of formatDateTime, for the
 * Dashboard's "Previous login" stat: split across two parts (date via
 * formatMemberSince, time via this) instead of forcing a wide column. */
export function formatTimeOnly(iso: string, language: SupportedLanguage): string {
    return formatHourMinute(new Date(iso), language);
}

// Intl locale per language for formatLongDate. en-GB, not en: plain "en"
// puts the month first ("September 16"), unlike every other date here.
const LONG_DATE_LOCALES: Record<SupportedLanguage, string> = { en: "en-GB", hi: "hi-IN", mr: "mr-IN", gu: "gu-IN" };

/** e.g. "Wednesday 16 September 2026", weekday and month names in the
 * active language, day before month. */
export function formatLongDate(date: Date | number, language: SupportedLanguage): string {
    const formatted = new Intl.DateTimeFormat(LONG_DATE_LOCALES[language], {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
    }).format(date);
    return formatNumber(formatted, language);
}

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 365 * 24 * 60 * 60],
    ["month", 30 * 24 * 60 * 60],
    ["week", 7 * 24 * 60 * 60],
    ["day", 24 * 60 * 60],
    ["hour", 60 * 60],
    ["minute", 60],
];

/** e.g. "now", "2 minutes ago", "3 days ago", in the active language. For
 * "how recently" values like a session's last seen time, shown alongside
 * formatDateTime's exact value. A timestamp slightly in the future (clock
 * skew between server and browser) reads as "now", never "in 2 seconds". */
export function formatRelativeTime(iso: string, language: SupportedLanguage, now: number = Date.now()): string {
    const seconds = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000));
    const rtf = new Intl.RelativeTimeFormat(language, { numeric: "auto" });
    for (const [unit, unitSeconds] of RELATIVE_UNITS) {
        if (seconds >= unitSeconds) return formatNumber(rtf.format(-Math.floor(seconds / unitSeconds), unit), language);
    }
    return formatNumber(rtf.format(0, "second"), language);
}
