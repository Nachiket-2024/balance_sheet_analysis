import React, { Suspense, lazy } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router";

// LoginPage loads eagerly because it is the common unauthenticated entry point.
// Other routes split at route level to keep the initial bundle to auth and shell.
import LoginPage from "../mystic_auth/auth/login/LoginPage";
const SignupPage = lazy(() => import("../mystic_auth/auth/signup/SignupPage"));
const VerifyAccountPage = lazy(() => import("../mystic_auth/auth/verify_account/VerifyAccountPage"));
const PasswordResetRequestPage = lazy(() => import("../mystic_auth/auth/password_reset_request/PasswordResetRequestPage"));
const PasswordResetConfirmPage = lazy(() => import("../mystic_auth/auth/password_reset_confirm/PasswordResetConfirmPage"));
const UsersPage = lazy(() => import("../mystic_auth/users/UsersPage"));
const PoliciesPage = lazy(() => import("../mystic_auth/policies/PoliciesPage"));
const AuditLogPage = lazy(() => import("../mystic_auth/audit_log/AuditLogPage"));
const AccountSettingsPage = lazy(() => import("../mystic_auth/account_settings/AccountSettingsPage"));
const NotFoundPage = lazy(() => import("../mystic_auth/status_pages/NotFoundPage"));
const NotAuthorizedPage = lazy(() => import("../mystic_auth/status_pages/NotAuthorizedPage"));

// App-owned pages. "/dashboard" renders mystic_auth's DashboardPage directly
// because Companies has its own permanent sidebar entry.
const DashboardPage = lazy(() => import("./app_sdk").then((m) => ({ default: m.DashboardPage })));
const CompaniesPage = lazy(() => import("./companies/CompaniesPage"));
const CompanyDetailPage = lazy(() => import("./companies/CompanyDetailPage"));

// Runs the current-user query once and mirrors it into the Zustand auth store.
// Keep this at the app root, not in arbitrary feature code.
import { useAuthSession } from "../mystic_auth/auth/current_user/useCurrentUserQuery";
// Real-time push for cross-tab/cross-device session revocation - same
// "call exactly once, at the app root" reasoning as useAuthSession above.
import { useSessionEventsStream } from "../mystic_auth/auth/session_lifecycle/useSessionEventsStream";

import { AppLayout, ProtectedRoute, PERMISSIONS, Toaster, useAuthStore, LoadingState, type NavItem } from "./sdk";
import { APP_PERMISSIONS } from "./access/permissions";

// order: 15 places Companies between Dashboard (10) and Users (20).
// extraNavItems is the supported shared-chrome extension point.
const EXTRA_NAV_ITEMS: NavItem[] = [
    { label: "Companies", to: "/companies", order: 15, permission: APP_PERMISSIONS.COMPANY_READ },
];

const App: React.FC = () => {
    useAuthSession();
    useSessionEventsStream();

    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    // null means the session check is still resolving.
    if (isAuthenticated === null) {
        return <LoadingState message="Checking session..." fullScreen />;
    }

    return (
        <Router>
            {/* Toast queue renderer. Portal rendering keeps it out of layout flow. */}
            <Toaster />

            <Suspense fallback={<LoadingState message="Loading..." fullScreen />}>
            <Routes>
                {/* Protected routes render the shell only after access is confirmed. */}
                {/* "/" redirects to "/dashboard" so sidebar highlighting stays correct. */}
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route
                    path="/dashboard"
                    element={
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <DashboardPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/companies"
                    element={
                        <ProtectedRoute permission={APP_PERMISSIONS.COMPANY_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <CompaniesPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/companies/:companyId"
                    element={
                        <ProtectedRoute permission={APP_PERMISSIONS.COMPANY_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <CompanyDetailPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/users"
                    element={
                        <ProtectedRoute permission={PERMISSIONS.USERS_LIST_ALL}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <UsersPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/policies"
                    element={
                        <ProtectedRoute permission={PERMISSIONS.POLICIES_READ}>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <PoliciesPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/audit-log"
                    element={
                        // No permission prop: every authenticated user can see
                        // their own audit trail. AuditLogPage gates "All users".
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <AuditLogPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/account-settings"
                    element={
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
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

                {/* ProtectedRoute sends authenticated users here when permission fails. */}
                <Route path="/not-authorized" element={<NotAuthorizedPage />} />

                <Route path="*" element={<NotFoundPage />} />
            </Routes>
            </Suspense>
        </Router>
    );
};

export default App;
