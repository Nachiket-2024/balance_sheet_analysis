import React, { useState } from "react";
import { Navigate } from "react-router";
import { useTranslation } from "react-i18next";

import { useAuthorization } from "./useAuthorization";
import { useAuthStore } from "../store/authStore";
import LoadingState from "../ui/feedback/LoadingState";

interface ProtectedRouteProps {
    children: React.ReactNode;
    // If set, the caller must also hold this action (checked via useAuthorization().can), e.g.
    // permission="policies:read". An array means "any of", for a route that more than one
    // independent action can legitimately reach (e.g. read OR create policies).
    // Omit for a route that only needs authentication.
    permission?: string | string[];
    // Passed through to can() alongside `permission`. Doesn't narrow the check yet: see
    // useAuthorization.ts's `can`.
    resourceType?: string;
}

/**
 * Ensures that child components are only accessible to authenticated users, and, when a
 * `permission` is given, only to callers who currently hold that permission too.
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, permission, resourceType }) => {
    const { t } = useTranslation("authorization");
    const { isAuthenticated, can } = useAuthorization();
    const permissionsPending = useAuthStore((s) => s.permissionsPending);
    const isAllowed = isAuthenticated === true && (!permission || can(permission, resourceType));

    // wasEverAllowed distinguishes never having had permission (stays false) from a live SSE
    // permissions_changed push (see useSessionEventsStream.ts's dropPermissions()) revoking
    // access after the route was already open (true by then). Updated directly in the render
    // body rather than a useEffect since it's purely derived from `isAllowed`. Both hooks run
    // unconditionally before any early return, so hook order stays stable.
    const [prevIsAllowed, setPrevIsAllowed] = useState(isAllowed);
    const [wasEverAllowed, setWasEverAllowed] = useState(isAllowed);
    if (isAllowed !== prevIsAllowed) {
        setPrevIsAllowed(isAllowed);
        if (isAllowed) setWasEverAllowed(true);
    }

    // Loader only while auth status is truly unknown. Permissions are set in the same store
    // update as isAuthenticated=true (see useAuthSession in useCurrentUserQuery.ts), so there's
    // no separate "permissions still loading" gap to handle.
    if (isAuthenticated === null) {
        return <LoadingState message={t("authorization:verifyingSession")} fullScreen />;
    }

    if (isAuthenticated === false) {
        // No return-to-previous-page state: every login lands on /dashboard regardless of how
        // the session ended, since LoginPage.tsx always redirects there.
        return <Navigate to="/login" replace />;
    }

    if (!isAllowed) {
        // A permissions_changed push clears the whole permission list even for an unrelated
        // change, so isAllowed can briefly read false without a real revoke. Show a loader
        // until the follow-up GET /auth/me confirms the route is actually forbidden.
        if (wasEverAllowed && permissionsPending) {
            return <LoadingState message={t("authorization:verifyingSession")} fullScreen />;
        }

        // Confirmed revoke: go straight home instead of the 403 page (which would misleadingly
        // suggest a bad direct link). `replace` drops the revoked route from history.
        if (wasEverAllowed) {
            return <Navigate to="/dashboard" replace />;
        }

        // Not /login: the caller is authenticated, just missing a permission.
        return <Navigate to="/not-authorized" replace />;
    }

    return <>{children}</>;
};

export default ProtectedRoute;
