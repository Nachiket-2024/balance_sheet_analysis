import React from "react";
import { Navigate } from "react-router";
import { useTranslation } from "react-i18next";

import { useAuthorization } from "./useAuthorization";
import LoadingState from "../ui/LoadingState";

interface ProtectedRouteProps {
    children: React.ReactNode;
    // If provided, the caller must also hold this action (via useAuthorization().can) in
    // addition to being authenticated, e.g. permission="policies:read" for a permission-gated route.
    // Omit for a route that only needs authentication.
    permission?: string;
    // Passed through to can() alongside `permission`: see useAuthorization.ts's `can` for why
    // this doesn't currently narrow the check (the cached permissions list has no resource-type
    // dimension of its own).
    resourceType?: string;
}

/**
 * Ensures that child components are only accessible to authenticated users, and, when a
 * `permission` is given, only to callers who currently hold that permission too.
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, permission, resourceType }) => {
    const { t } = useTranslation("authorization");
    const { isAuthenticated, can } = useAuthorization();

    // Show a loader only while authentication status is truly unknown: permissions are
    // populated in the same Zustand store update that sets isAuthenticated=true (see
    // useAuthSession in useCurrentUserQuery.ts), so there's no separate "permissions still
    // loading" gap to handle here. Never render protected (or unauthorized-redirect) content
    // before that's resolved, so there's no flash of either.
    if (isAuthenticated === null) {
        return <LoadingState message={t("authorization:verifyingSession")} fullScreen />;
    }

    if (isAuthenticated === false) {
        // Deliberately no `from`/return-to-previous-page state: every login
        // (whether after an explicit logout, a session that died from under
        // the user, or a fresh unauthenticated visit) lands on /dashboard,
        // never wherever the caller happened to be when they lost their
        // session - LoginPage.tsx always redirects there.
        return <Navigate to="/login" replace />;
    }

    // Deliberately NOT /login: the caller IS authenticated, just missing a permission, so
    // sending them back to a login form would be confusing and wouldn't fix anything.
    if (permission && !can(permission, resourceType)) {
        return <Navigate to="/not-authorized" replace />;
    }

    return <>{children}</>;
};

export default ProtectedRoute;
