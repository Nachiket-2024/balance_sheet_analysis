import React, { type ReactNode } from "react";

import { useAuthorization } from "./useAuthorization";
import { useCan } from "./useCan";

interface AuthorizedProps {
    permission: string;
    // Passed through to useCan; see useAuthorization.ts's `can` for why this doesn't currently
    // narrow the check: the cached permissions list has no resource-type dimension of its own.
    resourceType?: string;
    fallback?: ReactNode;
    children: ReactNode;
}

/**
 * Declarative wrapper for conditionally rendering UI based on a single permission: the
 * component equivalent of `useCan`, for call sites that read more naturally as JSX than as an
 * `if` inside a component body.
 *
 * While isAuthenticated is still unknown (the initial session check hasn't resolved yet),
 * renders nothing at all, never children, and never `fallback` either, since showing a "you
 * don't have permission" fallback before we've even confirmed the user's identity would itself
 * be a flash of incorrect state, just the opposite kind from prematurely showing protected
 * content.
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
