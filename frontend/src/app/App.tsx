import React, { Suspense, lazy } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from "react-router";
import { Flex, Heading, Text, VStack, Button } from "@chakra-ui/react";
import type { StackProps } from "@chakra-ui/react";

// LoginPage is loaded eagerly since it's the most common entry point for an
// unauthenticated visitor, so it shouldn't show a loading flash of its own
// on top of App's own session-check gate. Every other route is route-level
// code-split via React.lazy: none of them are needed until their route is
// actually visited, and splitting them keeps the initial bundle (and every
// unauthenticated visitor's download) limited to auth + the app shell.
import LoginPage from "../mystic_auth/auth/login/LoginPage";
const SignupPage = lazy(() => import("../mystic_auth/auth/signup/SignupPage"));
const VerifyAccountPage = lazy(() => import("../mystic_auth/auth/verify_account/VerifyAccountPage"));
const PasswordResetRequestPage = lazy(() => import("../mystic_auth/auth/password_reset_request/PasswordResetRequestPage"));
const PasswordResetConfirmPage = lazy(() => import("../mystic_auth/auth/password_reset_confirm/PasswordResetConfirmPage"));
const UsersPage = lazy(() => import("../mystic_auth/users/UsersPage"));
const PoliciesPage = lazy(() => import("../mystic_auth/policies/PoliciesPage"));
const AuditLogPage = lazy(() => import("../mystic_auth/audit_log/AuditLogPage"));
const ProfilePage = lazy(() => import("../mystic_auth/profile/ProfilePage"));

// This app's own domain pages (see docs/app/architecture/overview.md). "/dashboard"
// renders mystic_auth's own DashboardPage (via app_sdk.ts) directly, with no
// app-specific wrapper needed now that Companies has its own permanent
// sidebar entry (see EXTRA_NAV_ITEMS below) instead of a dashboard button.
const DashboardPage = lazy(() => import("./app_sdk").then((m) => ({ default: m.DashboardPage })));
const CompaniesPage = lazy(() => import("./companies/CompaniesPage"));
const CompanyDetailPage = lazy(() => import("./companies/CompanyDetailPage"));

// Runs the current-user query once and mirrors it into the Zustand auth
// store (see its own docstring for why this must be called exactly once,
// here at the app root). It's not re-exported from sdk.ts since it's meant to
// be called exactly once, here, not from arbitrary feature code.
import { useAuthSession } from "../mystic_auth/auth/current_user/useCurrentUserQuery";

import { AppLayout, ProtectedRoute, PERMISSIONS, Toaster, useAuthStore, LoadingState, type NavItem } from "./sdk";
import { APP_PERMISSIONS } from "./access/permissions";

// Sidebar link for this app's own Companies feature. order: 15 lands it
// between Dashboard (10) and mystic_auth's own Users (20). See
// docs/mystic_auth/template-usage/overview.md#shared-chrome-extension-points
// for why this goes through AppLayout's extraNavItems rather than editing
// mystic_auth/layout/navItems.ts directly.
const EXTRA_NAV_ITEMS: NavItem[] = [
    { label: "Companies", to: "/companies", order: 15, permission: APP_PERMISSIONS.COMPANY_READ },
];

const NotFoundPage: React.FC = () => {
    const navigate = useNavigate();
    return (
        <Flex align="center" justify="center" h="100vh" bg="bg.canvas" px={4} textAlign="center">
            <VStack {...({ spacing: 4 } as StackProps)}>
                <Heading color="fg.error" size="2xl">404</Heading>

                <Text fontSize="xl" fontWeight="medium">Oops! Page Not Found</Text>

                <Button
                    colorPalette="brand"
                    size="md"
                    fontWeight="bold"
                    onClick={() => navigate("/")}
                >
                    Go Home
                </Button>
            </VStack>
        </Flex>
    );
};

/**
 * NotAuthorizedPage
 * ----------------------------
 * The 403 page, where ProtectedRoute redirects an authenticated user who
 * lacks a route's required permission (see authorization/ProtectedRoute.tsx).
 * Deliberately a separate page from NotFoundPage: "you don't have
 * permission" and "this page doesn't exist" are different situations a
 * user shouldn't have to guess between.
 */
const NotAuthorizedPage: React.FC = () => {
    const navigate = useNavigate();
    return (
        <Flex align="center" justify="center" h="100vh" bg="bg.canvas" px={4} textAlign="center">
            <VStack {...({ spacing: 4 } as StackProps)}>
                <Heading color="fg.error" size="2xl">403</Heading>

                <Text fontSize="xl" fontWeight="medium">You don't have permission to view this page</Text>

                <Button
                    colorPalette="brand"
                    size="md"
                    fontWeight="bold"
                    onClick={() => navigate("/")}
                >
                    Go Home
                </Button>
            </VStack>
        </Flex>
    );
};

const App: React.FC = () => {
    useAuthSession();

    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    // isAuthenticated is null until the session check resolves; showing a
    // loading screen until then avoids a flash of unauthenticated content.
    if (isAuthenticated === null) {
        return <LoadingState message="Checking session..." fullScreen />;
    }

    return (
        <Router>
            {/* Toast queue renderer, mounted once at the app root (uses a
                Portal internally, so placement here doesn't affect layout) */}
            <Toaster />

            <Suspense fallback={<LoadingState message="Loading..." fullScreen />}>
            <Routes>
                {/* Protected routes require authentication. Each is wrapped
                    in AppLayout (sidebar + top bar) inside ProtectedRoute, so
                    the shell only ever renders once access has actually been
                    confirmed. */}
                {/* "/" itself is never a real page: redirect to "/dashboard"
                    so the URL and the Sidebar's active-item highlight (which
                    matches against "/dashboard") both stay correct. */}
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
                        // their own audit trail (see AuditLogPage's docstring
                        // for how the "All users" tab is gated separately).
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <AuditLogPage />
                            </AppLayout>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/profile"
                    element={
                        <ProtectedRoute>
                            <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
                                <ProfilePage />
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

                {/* Where ProtectedRoute sends an authenticated user who lacks
                    a route's required permission */}
                <Route path="/not-authorized" element={<NotAuthorizedPage />} />

                <Route path="*" element={<NotFoundPage />} />
            </Routes>
            </Suspense>
        </Router>
    );
};

export default App;