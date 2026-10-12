import { useAuthStore } from "../store/authStore";

/**
 * isAuthenticated: null = session not checked yet, true/false after.
 * role is metadata only: see backend/mystic_auth/authorization/permissions.py's docstring
 * for why role is never used to decide access.
 * permissions is a flat list of every action the caller currently holds.
 */
interface AuthorizationState {
    isAuthenticated: boolean | null;
    name: string | null;
    email: string | null;
    role: string | null;
    permissions: string[];
    /**
     * A single action string is a plain membership check. An array means "any of": true as
     * soon as one listed action is held, for a page/route reachable via more than one
     * independent action (e.g. viewing OR creating policies). See navItems.ts's Policies entry.
     */
    can: (action: string | string[], resourceType?: string) => boolean;
}

/**
 * Reads the caller's session/permissions from the Zustand auth store and shapes them into
 * the object every consumer (ProtectedRoute, Authorized, useCan) expects.
 *
 * `resourceType` is accepted for forward compatibility with the backend's richer
 * authorize(action, resource_type, resource, context) signature, but not used to filter here:
 * GET /auth/me returns a flat list of granted actions with no resource-type dimension. For a
 * check that depends on resource_type, ownership, or a condition (time/network/...), call
 * POST /authorization/batch-check instead of this in-memory cache, see authorizationService.ts.
 *
 * `can` fails closed: false while loading/unauthenticated, never "allowed" on unknown state.
 */
export function useAuthorization(): AuthorizationState {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const name = useAuthStore((s) => s.name);
    const email = useAuthStore((s) => s.email);
    const role = useAuthStore((s) => s.role);
    const permissions = useAuthStore((s) => s.permissions);

    const can = (action: string | string[], _resourceType?: string): boolean => {
        if (!isAuthenticated) return false;
        return Array.isArray(action) ? action.some((a) => permissions.includes(a)) : permissions.includes(action);
    };

    return { isAuthenticated, name, email, role, permissions, can };
}
