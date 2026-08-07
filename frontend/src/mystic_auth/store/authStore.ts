import { create } from "zustand";

import type { CurrentUserProfile } from "../auth/current_user/current_user_types";

/**
 * The single client-side source of truth for "who is logged in right now and what can they do".
 * Populated from GET /auth/me and kept in sync by every mutation that changes the session
 * (login/logout/logout-all) and by the axios 401 interceptor (see auth/session_lifecycle/setupAuthInterceptor.ts).
 */
interface AuthState {
    /** null = session not checked yet, true/false after. */
    isAuthenticated: boolean | null;
    name: string | null;
    email: string | null;
    // Metadata only, see backend/mystic_auth/authorization/permissions.py's own docstring for why role
    // is never used to decide access.
    role: string | null;
    /** Flat list of every action string the caller currently holds via their active policies. */
    permissions: string[];
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
    /** Full reset to the initial (unchecked) state. */
    reset: () => void;
}

const initialProfile = {
    name: null,
    email: null,
    role: null,
    permissions: [] as string[],
    hasPassword: false,
};

export const useAuthStore = create<AuthState>((set) => ({
    isAuthenticated: null,
    ...initialProfile,

    setAuthenticated: (isAuthenticated) =>
        set(isAuthenticated ? { isAuthenticated } : { isAuthenticated, ...initialProfile }),

    setProfile: (profile) =>
        set({
            name: profile.name,
            email: profile.email,
            role: profile.role,
            permissions: profile.permissions ?? [],
            hasPassword: profile.has_password,
        }),

    clearProfile: () => set({ ...initialProfile }),

    reset: () => set({ isAuthenticated: null, ...initialProfile }),
}));
