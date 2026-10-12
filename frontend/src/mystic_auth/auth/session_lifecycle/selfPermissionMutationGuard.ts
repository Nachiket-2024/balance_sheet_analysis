// Tracks whether THIS tab just granted/revoked a policy or permission against its own
// account (PolicyFormDialog/UserPoliciesDialog/UserPermissionsDialog and their bulk
// equivalents, when the acting caller's own email is among the targets).
//
// Why: the backend's "permissions_changed" SSE event looks identical whether the
// change came from this tab or another session. useSessionEventsStream.ts reacts
// to it by synchronously zeroing the permissions list (dropPermissions()) so a tab
// that genuinely lost access fails closed instantly. But firing that wipe for a change
// THIS tab just made itself (e.g. a caller granting themselves a permission) would
// momentarily zero a permission the route still holds, and ProtectedRoute would read
// that as a live revoke and bounce to /dashboard before the refetch corrects it.
//
// This tab already knows the true outcome from its own mutation response, so skipping
// dropPermissions() for its own echo loses no security guarantee: a genuine
// self-triggered loss is still caught once CURRENT_USER_QUERY_KEY's own invalidation
// resolves.
//
// Consumed on first read, not just time-windowed: the SSE event carries no detail
// about which permission changed or who changed it, so there's no way to confirm an
// incoming event actually is this tab's own echo versus a coincidentally-timed
// unrelated change from another session. A plain elapsed-time check would swallow every
// event in the window, not just the one echo it exists to cover. Clearing the flag
// after one check bounds the exposure to at most one skipped event per self-mutation.
let lastSelfMutationAt: number | null = null;

// Generous enough to cover the round trip from this tab's mutation response to the SSE
// event for that same change arriving back, without staying armed long enough to also
// swallow an unrelated revoke landing moments later (bounded further by the single-use
// consumption above, not just this window).
const RECENT_SELF_MUTATION_WINDOW_MS = 5000;

export function markSelfPermissionMutation(): void {
    lastSelfMutationAt = Date.now();
}

/** Single-use: the first check after a self-mutation consumes the flag,
 * whether or not it was within the window, so at most one incoming event
 * is ever treated as the self-echo. */
export function wasSelfPermissionMutationRecent(): boolean {
    if (lastSelfMutationAt === null) return false;
    const withinWindow = Date.now() - lastSelfMutationAt < RECENT_SELF_MUTATION_WINDOW_MS;
    lastSelfMutationAt = null;
    return withinWindow;
}

/** Test-only: clears tracked state between test cases. */
export function resetSelfPermissionMutationGuardForTests(): void {
    lastSelfMutationAt = null;
}
