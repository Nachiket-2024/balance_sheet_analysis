import { create } from "zustand";

import type { CurrentUserProfile } from "../auth/current_user/current_user_types";

// The single client-side source of truth for "who is logged in right now and what can
// they do". Populated from GET /auth/me and kept in sync by every mutation that
// changes the session (login/logout/logout-all) and by the axios 401 interceptor
// (see auth/session_lifecycle/setupAuthInterceptor.ts).
interface AuthState {
    /** null = session not checked yet, true/false after. */
    isAuthenticated: boolean | null;
    /** Timestamp of the latest successful session establishment. Used to ignore
     * a stale pre-login 401 that resolves after login has completed. */
    authenticatedAt: number | null;
    name: string | null;
    email: string | null;
    // Metadata only; see permissions.py's own docstring for why role is never used
    // to decide access.
    role: string | null;
    /** Flat list of every action string the caller currently holds via their active policies. */
    permissions: string[];
    /** True from the instant dropPermissions() zeroes the list until the follow-up
     *  GET /auth/me resolves (setProfile) or fails (clearProfile/setAuthenticated(false)/
     *  reset). Signals "permissions is known-stale, don't treat the empty list as
     *  authoritative yet" - see ProtectedRoute.tsx: without this, an unrelated
     *  permissions_changed push would transiently zero `permissions`, `can()` would
     *  briefly report false, and the route would bounce to /dashboard before the
     *  refetch had a chance to prove it was never affected. */
    permissionsPending: boolean;
    /** Whether the account currently has a usable password credential:
     *  false for an OAuth-only account. See CurrentUserProfile. */
    hasPassword: boolean;
    /** Directly set auth status (used after login/logout/a 401). Setting
     *  false also clears the profile, so a stale permissions list can never
     *  outlive the session it came from. */
    setAuthenticated: (isAuthenticated: boolean) => void;
    /** Store the caller's own profile/permissions from a successful
     *  GET /auth/me response. */
    setProfile: (profile: CurrentUserProfile) => void;
    /** Clear the caller's own profile/permissions without touching
     *  isAuthenticated. */
    clearProfile: () => void;
    /** Synchronously fail-closed on every permission check (ProtectedRoute, IfCan,
     *  the sidebar's nav filter, ...) without waiting on a network round-trip. Used
     *  the instant a permissions_changed server push arrives (see
     *  useSessionEventsStream.ts): the new permission list isn't known yet, only that
     *  it changed, so "holds nothing" is the safe assumption until GET /auth/me lands.
     *  isAuthenticated/profile are left untouched, this is not a logout. Also flips
     *  permissionsPending on. */
    dropPermissions: () => void;
    /** Full reset to the initial (unchecked) state. */
    reset: () => void;
}

const initialProfile = {
    name: null,
    email: null,
    role: null,
    permissions: [] as string[],
    hasPassword: false,
    permissionsPending: false,
};

export const useAuthStore = create<AuthState>((set) => ({
    isAuthenticated: null,
    authenticatedAt: null,
    ...initialProfile,

    setAuthenticated: (isAuthenticated) =>
        set(
            isAuthenticated
                ? { isAuthenticated, authenticatedAt: Date.now() }
                : { isAuthenticated, authenticatedAt: null, ...initialProfile },
        ),

    setProfile: (profile) =>
        set({
            name: profile.name,
            email: profile.email,
            role: profile.role,
            permissions: profile.permissions ?? [],
            hasPassword: profile.has_password,
            permissionsPending: false,
        }),

    clearProfile: () => set({ ...initialProfile }),

    dropPermissions: () => set({ permissions: [], permissionsPending: true }),

    reset: () => set({ isAuthenticated: null, authenticatedAt: null, ...initialProfile }),
}));
