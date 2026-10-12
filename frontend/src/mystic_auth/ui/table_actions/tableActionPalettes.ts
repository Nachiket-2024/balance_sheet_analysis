// Covers every palette this app passes to a row-action button. Every
// palette reads as a plain neutral icon button at rest - muted border/bg/
// text, matching `neutral` - and only takes on its color on hover/focus, as
// a light tint (same shape as `neutral`'s own hover:bg-brand-subtle/
// hover:text-brand-fg), not a solid saturated fill with forced white text.
// A table row doesn't show a permanent row of colored chips, and hovering
// one doesn't flip it into a jarring solid block either - every action
// button in a row hovers the same way, just tinted toward its own color.
// The color itself still carries the same meaning as before (Delete red,
// Reactivate green, Deactivate yellow, Edit orange, View blue, ...) - only
// the resting state and hover weight changed, not what each color means. A
// plain constants module (not a component) so both TableActionButton and
// TableActionIconButton can import it without tripping react-refresh's
// only-export-components rule.
const NEUTRAL_REST = "border border-border-strong bg-bg-surface text-fg-muted shadow-[0_1px_2px_rgba(15,23,42,0.06)]";

export const DESTRUCTIVE_TABLE_ACTION_CLASSNAME =
    "border-red-400 text-fg-error hover:bg-red-600 hover:border-red-600 hover:text-white dark:border-red-400 dark:hover:bg-red-600 dark:hover:border-red-600 dark:hover:text-white";

export const TABLE_ACTION_PALETTE_STYLES = {
    // Plain navigation/informational actions (View, Edit, Policies,
    // Permissions, ...): neutral at rest, brand-tinted on hover so it still
    // reads as an actionable control without competing with the row's real
    // status colors (verified/unverified, deactivated, destructive).
    neutral: `${NEUTRAL_REST} hover:border-brand-emphasized hover:bg-brand-subtle hover:text-brand-fg dark:hover:text-[var(--brand-200)]`,
    // Delete/Purge.
    red: `${NEUTRAL_REST} hover:border-red-500 hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-950 dark:hover:text-red-300`,
    // Reactivate.
    green: `${NEUTRAL_REST} hover:border-green-500 hover:bg-green-100 hover:text-green-700 dark:hover:bg-green-950 dark:hover:text-green-300`,
    // Deactivate: a caution, reversible action - distinct from both Delete
    // (red, permanent) and Reactivate (green, a positive/enable action that
    // Deactivate is the opposite of, not a shade of). Not reused across
    // Edit's orange or View's blue either, since either can share a row with
    // Deactivate (Users: Deactivate+Permissions/orange; Policies: Deactivate+
    // Edit/orange+View/blue).
    yellow: `${NEUTRAL_REST} hover:border-yellow-500 hover:bg-yellow-100 hover:text-yellow-800 dark:hover:bg-yellow-950 dark:hover:text-yellow-300`,
    // Edit.
    orange: `${NEUTRAL_REST} hover:border-orange-500 hover:bg-orange-100 hover:text-orange-700 dark:hover:bg-orange-950 dark:hover:text-orange-300`,
    // View.
    blue: `${NEUTRAL_REST} hover:border-blue-500 hover:bg-blue-100 hover:text-blue-700 dark:hover:bg-blue-950 dark:hover:text-blue-300`,
    // Tracks whatever the app's brand color currently is (semantic
    // --brand-* tokens, which already switch under .dark), unlike the fixed
    // scales above - for callers like DashboardIdentityCard's shortcut
    // buttons that want to read as "brand accent" on hover.
    brand: `${NEUTRAL_REST} hover:border-brand-emphasized hover:bg-brand-subtle hover:text-brand-fg dark:hover:text-[var(--brand-200)]`,
    // Policies. Cyan, not a reused color, so it reads as its own action
    // distinct from whatever the app's brand color currently is - stock
    // purple sits close to a violet brand pick, so purple doesn't reliably
    // read as "its own color" the way a fixed cyan does.
    cyan: `${NEUTRAL_REST} hover:border-cyan-500 hover:bg-cyan-100 hover:text-cyan-700 dark:hover:bg-cyan-950 dark:hover:text-cyan-300`,
} as const;
