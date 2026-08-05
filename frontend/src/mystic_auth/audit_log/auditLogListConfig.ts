/**
 * The pagination size, filter-placeholder value, timestamp formatting, and
 * page-count/bool-filter parsing every audit-log list table needs to render
 * itself consistently: all four section components, in both
 * authorization_log/ and security_log/, depend on these same five things
 * identically, so this is the one place they live rather than each tab
 * duplicating them.
 */

export const PAGE_SIZE = 25;
export const ALL_VALUE = "";

export function formatTimestamp(iso: string): string {
    return new Date(iso).toLocaleString();
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
