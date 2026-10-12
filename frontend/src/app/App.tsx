import React, { Suspense, useEffect, useState } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router";
import { Activity, Building2, Scale } from "lucide-react";

// LoginPage loads eagerly since it's the most common entry point for an
// unauthenticated visitor and shouldn't flash on top of the session-check
// gate below. Every other route is lazy-loaded so the initial bundle stays
// limited to auth + the app shell.
import LoginPage from "../mystic_auth/auth/login/LoginPage";
import { trackedLazy } from "../mystic_auth/ui/routing/trackedLazy";
const LandingPage = trackedLazy(() => import("./landing_page/LandingPage"));
const SignupPage = trackedLazy(() => import("../mystic_auth/auth/signup/SignupPage"));
const VerifyAccountPage = trackedLazy(() => import("../mystic_auth/auth/verify_account/VerifyAccountPage"));
const PasswordResetRequestPage = trackedLazy(() => import("../mystic_auth/auth/password_reset_request/PasswordResetRequestPage"));
const PasswordResetConfirmPage = trackedLazy(() => import("../mystic_auth/auth/password_reset_confirm/PasswordResetConfirmPage"));
const ConfirmDeleteAccountPage = trackedLazy(() => import("../mystic_auth/account_settings/confirm_delete/ConfirmDeleteAccountPage"));
const DashboardPage = trackedLazy(() => import("./app_sdk").then((m) => ({ default: m.DashboardPage })));
const UsersPage = trackedLazy(() => import("../mystic_auth/users/UsersPage"));
const PoliciesPage = trackedLazy(() => import("../mystic_auth/policies/PoliciesPage"));
const PermissionsPage = trackedLazy(() => import("../mystic_auth/permissions/PermissionsPage"));
const RateLimitsPage = trackedLazy(() => import("../mystic_auth/rate_limits/RateLimitsPage"));
const AuditLogPage = trackedLazy(() => import("../mystic_auth/audit_log/AuditLogPage"));
const AccountSettingsPage = trackedLazy(() => import("../mystic_auth/account_settings/AccountSettingsPage"));
const NotFoundPage = trackedLazy(() => import("./status_pages/NotFoundPage"));
const NotAuthorizedPage = trackedLazy(() => import("./status_pages/NotAuthorizedPage"));
const PrivacyPolicyPage = trackedLazy(() => import("./legal/PrivacyPolicyPage"));
const TermsOfServicePage = trackedLazy(() => import("./legal/TermsOfServicePage"));

// App-owned pages. "/dashboard" renders mystic_auth's DashboardPage directly
// because Companies has its own permanent sidebar entry.
const CompaniesPage = trackedLazy(() => import("./companies/CompaniesPage"));
const CompanyDetailPage = trackedLazy(() => import("./companies/CompanyDetailPage"));
const ComparisonPage = trackedLazy(() => import("./companies/ComparisonPage"));
const LlmOperationsPage = trackedLazy(() => import("./llm/LlmOperationsPage"));

// Runs the current-user query once and mirrors it into the Zustand auth
// store. Not re-exported from sdk.ts since it must only be called here,
// at the app root, not from arbitrary feature code.
import { useAuthSession } from "../mystic_auth/auth/current_user/useCurrentUserQuery";
// Real-time push for cross-tab/cross-device session revocation. Same
// "call once, at the app root" reasoning as useAuthSession above.
import { useSessionEventsStream } from "../mystic_auth/auth/session_lifecycle/useSessionEventsStream";

import { AppLayout, ProtectedRoute, PERMISSIONS, Toaster, useAuthStore, CommandPalette, type NavItem } from "./sdk";
import { APP_PERMISSIONS } from "./access/permissions";
import RouteProgressBar from "../mystic_auth/ui/routing/RouteProgressBar";
import RouteFadeIn from "../mystic_auth/ui/routing/RouteFadeIn";
import OfflineBanner from "../mystic_auth/ui/network/OfflineBanner";

// order: 15 places Companies between Dashboard (10) and Users (20).
// extraNavItems is the supported shared-chrome extension point. label is a
// "namespace:key" translation key, not a literal string: Sidebar.tsx
// resolves it the same way it resolves its own built-in items' labels (see
// NavItem's own doc comment in mystic_auth/layout/navItems.ts), so this
// follows the user's chosen language instead of always rendering "Companies".
const EXTRA_NAV_ITEMS: NavItem[] = [
    { label: "companies:navLabel", to: "/companies", order: 15, permission: APP_PERMISSIONS.COMPANY_READ, icon: Building2 },
    { label: "companies:comparisonNavLabel", to: "/comparison", order: 16, permission: APP_PERMISSIONS.BALANCE_SHEET_READ, icon: Scale },
    { label: "llm:operationsNavLabel", to: "/llm-operations", order: 17, permission: APP_PERMISSIONS.LLM_USAGE_READ_ALL, icon: Activity },
];

const App: React.FC = () => {
    useAuthSession();
    useSessionEventsStream();

    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    // Cmd+K / Ctrl+K quick-jump palette. Listener lives here (not inside
    // CommandPalette) so the shortcut is clearly global. Ignored while
    // unauthenticated since every palette destination is a protected route.
    const [isPaletteOpen, setIsPaletteOpen] = useState(false);
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!isAuthenticated) return;
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setIsPaletteOpen((open) => !open);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isAuthenticated]);

    // Passed to every AppLayout below so Navbar's search-bar trigger opens
    // the same palette instance the keydown listener above toggles.
    const openCommandPalette = () => setIsPaletteOpen(true);

    // isAuthenticated is null until the session check resolves; showing a
    // loading screen until then avoids a flash of unauthenticated content.
    if (isAuthenticated === null) {
        // The static boot shell covers this state until the first route
        // commits. Keeping the React tree empty here avoids showing a second
        // full-screen loader immediately after the HTML loader.
        return null;
    }

    return (
        <Router>
            {/* Toast queue renderer (uses a Portal, so placement here doesn't affect layout) */}
            <Toaster />

            {/* Top-of-viewport loading bar. Mounted here so it overlays the
                current page during a lazy-route navigation instead of the
                Suspense fallback below blanking it. */}
            <RouteProgressBar />

            {/* Fixed bottom banner reflecting networkStatusStore's isOnline
                flag, visible regardless of which page/dialog is on screen. */}
            <OfflineBanner />

            <CommandPalette isOpen={isPaletteOpen} onClose={() => setIsPaletteOpen(false)} extraNavItems={EXTRA_NAV_ITEMS} />

            {/* react-router wraps navigation in React.startTransition, so a
                click to a not-yet-loaded lazy route defers instead of
                blanking the current page. The single HTML boot shell covers
                the initial session and first lazy-route load. */}
            <RouteFadeIn>
            <Suspense fallback={null}>
            <Routes>
                {/* Protected routes require authentication. Each wraps
                    AppLayout (sidebar + top bar) inside ProtectedRoute, so
                    the shell only renders once access is confirmed.

                    Adding your own feature routes? Give AppLayout an
                    `extraNavItems` prop (NavItem shape from sdk.ts, e.g.
                    `[{ label: "Projects", to: "/projects", permission:
                    APP_PERMISSIONS.PROJECTS_READ }]`) instead of editing the
                    upstream-owned mystic_auth/layout/app_layout/navItems.ts.
                    Define the array once above this Routes block and reuse
                    the same reference on every AppLayout usage, so the
                    sidebar doesn't reshape while navigating. Pass it to
                    CommandPalette too (plus `extraSearchItems` for
                    in-page content) so palette search matches the sidebar.
                    See docs/mystic_auth/template-usage/frontend-customization.md#shared-chrome-extension-points. */}
                {/* "/" is the pre-auth landing page, not a redirect into the
                    app - it self-redirects an already-signed-in visitor to
                    /dashboard, so Sidebar's active-item highlight only ever
                    has to match routes that render the app shell. */}
                <Route path="/" element={<LandingPage />} />
                <Route
                    path="/dashboard"
                    element={
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <DashboardPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/companies"
                    element={
                        <ProtectedRoute permission={APP_PERMISSIONS.COMPANY_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <CompaniesPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/companies/:companyId"
                    element={
                        <ProtectedRoute permission={APP_PERMISSIONS.COMPANY_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <CompanyDetailPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/comparison"
                    element={
                        <ProtectedRoute permission={APP_PERMISSIONS.BALANCE_SHEET_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <ComparisonPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/llm-operations"
                    element={
                        <ProtectedRoute permission={APP_PERMISSIONS.LLM_USAGE_READ_ALL}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <LlmOperationsPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/users"
                    element={
                        <ProtectedRoute permission={PERMISSIONS.USERS_LIST_ALL}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <UsersPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/policies"
                    element={
                        // Any of read/create, not read alone - see
                        // navItems.ts's matching Policies entry for why.
                        <ProtectedRoute permission={[PERMISSIONS.POLICIES_READ, PERMISSIONS.POLICIES_CREATE]}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <PoliciesPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/permissions"
                    element={
                        <ProtectedRoute permission={PERMISSIONS.PERMISSIONS_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <PermissionsPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/rate-limits"
                    element={
                        <ProtectedRoute permission={PERMISSIONS.RATE_LIMITS_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <RateLimitsPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/audit-log"
                    element={
                        // No permission prop: every authenticated user can see
                        // their own audit trail (the "All users" tab is gated
                        // separately, see AuditLogPage). Added your own PBAC
                        // resource types/actions? Pass AuditLogPage
                        // `extraResourceTypes`/`extraActions` instead of
                        // hand-editing authorizationLogResourceTypes.ts.
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <AuditLogPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/account-settings"
                    element={
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
                                <AccountSettingsPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />

                <Route path="/login" element={<LoginPage />} />
                <Route path="/signup" element={<SignupPage />} />
                <Route path="/verify-account" element={<VerifyAccountPage />} />
                <Route path="/password-reset-request" element={<PasswordResetRequestPage />} />

                {/* Matches backend email link format */}
                <Route path="/reset-password" element={<PasswordResetConfirmPage />} />

                {/* Matches account_deletion_service.py's deletion_url */}
                <Route path="/confirm-delete" element={<ConfirmDeleteAccountPage />} />

                <Route path="/privacy" element={<PrivacyPolicyPage />} />
                <Route path="/terms" element={<TermsOfServicePage />} />

                {/* Where ProtectedRoute sends an authenticated user who lacks
                    a route's required permission */}
                <Route path="/not-authorized" element={<NotAuthorizedPage />} />

                <Route path="*" element={<NotFoundPage />} />
            </Routes>
            </Suspense>
            </RouteFadeIn>
        </Router>
    );
};

export default App;
