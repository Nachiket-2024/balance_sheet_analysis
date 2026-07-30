import { useAuthStore } from "../store/authStore";

/**
 * isAuthenticated: null = session not checked yet, true/false after.
 * role is metadata only, see backend/mystic_auth/authorization/permissions.py's
 * own docstring for why role is never used to decide access.
 * permissions is a flat list of every action string the caller currently
 * holds via their active policies.
 */
interface AuthorizationState {
    isAuthenticated: boolean | null;
    name: string | null;
    email: string | null;
    role: string | null;
    permissions: string[];
    can: (action: string, resourceType?: string) => boolean;
}

/**
 * Reads the caller's session/permissions from the Zustand auth store:
 * a module-level singleton reachable from anywhere, so this hook just
 * shapes its fields into the object every consumer (ProtectedRoute,
 * Authorized, useCan) expects.
 *
 * `resourceType` is accepted for forward compatibility with the backend's
 * richer authorize(action, resource_type, resource, context) signature, but
 * NOT used to filter here: GET /auth/me returns a flat list of granted
 * actions with no resource-type dimension of its own. For a check that
 * genuinely depends on resource_type, ownership, or a condition
 * (time/network/...), call the real backend endpoint
 * (POST /authorization/batch-check) instead of this in-memory cache, see
 * authorization/authorizationService.ts.
 *
 * `can` fails closed: false while loading/unauthenticated, never "allowed"
 * on an unknown state.
 */
export function useAuthorization(): AuthorizationState {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const name = useAuthStore((s) => s.name);
    const email = useAuthStore((s) => s.email);
    const role = useAuthStore((s) => s.role);
    const permissions = useAuthStore((s) => s.permissions);

    const can = (action: string, _resourceType?: string): boolean => {
        return !!isAuthenticated && permissions.includes(action);
    };

    return { isAuthenticated, name, email, role, permissions, can };
}
