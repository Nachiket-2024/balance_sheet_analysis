import React from "react";
import { Stack, Heading, Text, StackSeparator } from "@chakra-ui/react";
import { Link, useSearchParams } from "react-router";

import PasswordResetConfirmForm from "./PasswordResetConfirmForm";

// Shared surface styling (theme surface/border tokens): replaces this
// page's own hand-rolled bg="white"/boxShadow="lg" card.
import Card from "../../ui/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/AuthLayout";

const PasswordResetConfirmPage: React.FC = () => {
    const [searchParams] = useSearchParams();
    const token = searchParams.get("token") || "";

    const hasTokenFromUrl = !!token;

    return (
        <AuthLayout>
            <Card w="450px" maxW="md" p={{ base: 5, md: 7 }}>
                <Stack align="center" textAlign="center" separator={<StackSeparator />}>
                    <Heading size="xl" color="brand.fg">
                        Reset Password
                    </Heading>

                    {hasTokenFromUrl ? (
                        <Text fontSize="md" color="fg.muted">
                            Enter your new password below.
                        </Text>
                    ) : (
                        <Text fontSize="md" color="fg.muted">
                            Enter the token from your email and your new password below.
                        </Text>
                    )}

                    <PasswordResetConfirmForm token={token} />

                    <Text fontSize="16px" color="fg.muted">
                        Remember your password?{" "}
                        <Link to="/login" style={{ color: "var(--chakra-colors-brand-fg)", fontWeight: 600 }}>
                            Back to Login
                        </Link>
                    </Text>
                </Stack>
            </Card>
        </AuthLayout>
    );
};

export default PasswordResetConfirmPage;
