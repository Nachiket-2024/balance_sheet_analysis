/**
 * Generic date/time formatting, no feature ownership: shared by DashboardPage
 * (member-since, last-login) and ManageSessionsCard (signed-in/last-seen
 * columns), and any future feature that needs the same fixed-locale display.
 * Locale pinned to en-US (unlike AuditLogPage's formatTimestamp, which
 * deliberately follows the browser's locale for a full log table) so these
 * fixed-format stats read the same for every viewer regardless of their
 * system locale.
 */

/** e.g. "Jan 15, 2026". */
export function formatMemberSince(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** e.g. "Jul 25, 2026, 8:58 PM" - full date, year, and time together: a
 * relative "2h ago" reads fine for a login just now, but is ambiguous for a
 * login weeks old and useless for comparing several sessions against each
 * other - an actual timestamp always answers "when, exactly". */
export function formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
    });
}

/** e.g. "4:23 PM" - the time-only half of formatDateTime, for the
 * Dashboard's "Last login" stat: that stat sits in a narrow fixed-width
 * column next to two much shorter stats, so the full "Aug 1, 2026, 4:23 PM"
 * string is split across two lines (date via formatMemberSince above, time
 * via this) instead of forcing the column wide enough for one long line. */
export function formatTimeOnly(iso: string): string {
    return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
}
