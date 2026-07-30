import React from "react";
import { useNavigate, Link, Navigate } from "react-router";
import { Stack, Heading, Text, StackSeparator } from "@chakra-ui/react";

import LoginForm from "./LoginForm";
import OAuth2Button from "../oauth2/OAuth2LoginButton";
import { useAuthStore } from "../../store/authStore";

// Shared surface styling (theme surface/border tokens): replaces this
// page's own hand-rolled bg="white"/boxShadow="lg" card.
import Card from "../../ui/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/AuthLayout";

// This page reads isAuthenticated from the Zustand auth store, the single
// source of truth for "is anyone logged in right now" regardless of method
// (password or Google), rather than gating rendering on any per-method
// loading flag, which previously caused LoginForm to unmount mid-typing on
// unrelated session-check requests.
const LoginPage: React.FC = () => {
    const navigate = useNavigate();
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    if (isAuthenticated) return <Navigate to="/dashboard" replace />;

    const handleLoginSuccess = () => {
        navigate("/dashboard", { replace: true });
    };

    // No page-level error banner here: LoginForm and OAuth2Button each
    // surface their own mutation errors, so a shared banner would either
    // duplicate one of them or never fire.
    return (
        <AuthLayout>
            <Card w="450px" maxW="md" p={{ base: 5, md: 7 }}>
                <Stack
                    align="center"
                    textAlign="center"
                    gap={3}
                    separator={<StackSeparator />}
                >
                    {/* Kept smaller than AuthLayout's own APP_NAME heading directly
                        above, so the two don't compete and the page fits a normal
                        laptop viewport without scrolling. */}
                    <Heading size="xl" color="brand.fg">Welcome</Heading>
                    <Text fontSize="md" color="fg.muted">
                        Sign in to continue to your dashboard
                    </Text>

                    <LoginForm onSuccess={handleLoginSuccess} />
                    <OAuth2Button onSuccess={handleLoginSuccess} />

                    <Text fontSize="16px" color="fg.muted">
                        Don't have an account?{" "}
                        <Link to="/signup" style={{ color: "var(--chakra-colors-brand-fg)", fontWeight: 600 }}>
                            Sign Up
                        </Link>
                    </Text>
                </Stack>
            </Card>
        </AuthLayout>
    );
};

export default LoginPage;
