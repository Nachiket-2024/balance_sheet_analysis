/**
 * sessionRotationGuard
 * ----------------------------
 * Tracks whether a request that rotates the current session's cookies (right
 * now: only the "set/change password" PUT /users/me, see
 * useUpdateMyAccountMutation.ts) is in flight.
 *
 * Why this needs to exist: that endpoint bumps the account's Redis version
 * (invalidating every existing token, including this device's own) before
 * minting and returning fresh cookies for the exempted chain. Between those
 * two moments, any *other* request already in flight with the old
 * access/refresh cookies (a background query refetch, this same mutation's
 * own onSuccess invalidation, etc.) can 401 and then fail its silent refresh
 * too, since the old refresh cookie's account_ver is momentarily stale until
 * the rotating request's response actually lands and the browser applies its
 * Set-Cookie headers. Without this, setupAuthInterceptor.ts would treat that
 * timing loss as a real session death and show "Your session has expired"
 * even though the device was never actually logged out.
 *
 * Deliberately narrow: only gates the interceptor's *last-resort* fallback
 * (see its own comment), never suppresses a 401 that's genuinely terminal -
 * once the tracked request settles (plus a short grace window, see
 * RECENTLY_ROTATED_GRACE_MS below), a still-failing refresh is treated as
 * real.
 */
let pendingRotation: Promise<unknown> | null = null;
let rotationSettledAt: number | null = null;

// The rotating request settling only means ITS OWN response (and therefore
// its Set-Cookie headers) has landed - it says nothing about any OTHER
// request that was independently in flight at the same time (a background
// poll, a sidebar permissions fetch, ...) using the same old cookies. That
// request's own 401 can still be working its way back from the server a
// few ticks after the rotation itself resolved, purely due to normal
// network/scheduling jitter, not because the session actually died. Without
// this grace window, such a straggler finds pendingRotation already cleared
// and falls straight through to "session expired" even though a plain
// retry (cookies are already fresh by then) would have succeeded.
const RECENTLY_ROTATED_GRACE_MS = 3000;

export function trackSessionRotatingRequest<T>(request: Promise<T>): Promise<T> {
    const tracked = request.catch(() => undefined);
    pendingRotation = tracked;
    tracked.finally(() => {
        if (pendingRotation === tracked) pendingRotation = null;
        rotationSettledAt = Date.now();
    });
    return request;
}

export function getPendingSessionRotation(): Promise<unknown> | null {
    return pendingRotation;
}

/** True while a rotation is in flight, or settled recently enough that a
 * fresh 401 might just be a straggler request that lost the race against
 * it (see RECENTLY_ROTATED_GRACE_MS above). */
export function wasSessionRecentlyRotated(): boolean {
    if (pendingRotation) return true;
    return rotationSettledAt !== null && Date.now() - rotationSettledAt < RECENTLY_ROTATED_GRACE_MS;
}

/** Test-only: clears tracked rotation state between test cases so one
 * test's tracked rotation can't leak its grace window into the next. */
export function resetSessionRotationGuardForTests(): void {
    pendingRotation = null;
    rotationSettledAt = null;
}
