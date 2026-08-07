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
 * once the tracked request settles, a still-failing refresh is treated as
 * real.
 */
let pendingRotation: Promise<unknown> | null = null;

export function trackSessionRotatingRequest<T>(request: Promise<T>): Promise<T> {
    const tracked = request.catch(() => undefined);
    pendingRotation = tracked;
    tracked.finally(() => {
        if (pendingRotation === tracked) pendingRotation = null;
    });
    return request;
}

export function getPendingSessionRotation(): Promise<unknown> | null {
    return pendingRotation;
}
