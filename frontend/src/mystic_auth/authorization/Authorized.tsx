import React, { type ReactNode } from "react";

import { useAuthorization } from "./useAuthorization";
import { useCan } from "./useCan";

interface AuthorizedProps {
    /** A single action, or an array meaning "any of" - see useAuthorization's `can`. */
    permission: string | string[];
    // Passed through to useCan. Doesn't narrow the check yet: see useAuthorization.ts's `can`.
    resourceType?: string;
    fallback?: ReactNode;
    children: ReactNode;
}

/**
 * Declarative version of `useCan`, for JSX call sites: renders children if the permission is
 * held, otherwise fallback.
 *
 * While isAuthenticated is still unknown (session check hasn't resolved), renders nothing,
 * not children or fallback, so we never flash a "no permission" message before we know who
 * the user is.
 */
export const Authorized: React.FC<AuthorizedProps> = ({
    permission,
    resourceType,
    fallback = null,
    children,
}) => {
    const { isAuthenticated } = useAuthorization();
    const can = useCan(permission, resourceType);

    if (isAuthenticated === null) {
        return null;
    }

    return can ? <>{children}</> : <>{fallback}</>;
};
