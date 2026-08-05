import React from "react";
import { useSearchParams, useNavigate } from "react-router";
import { Heading, Text, VStack, Stack, StackSeparator } from "@chakra-ui/react";

import VerifyAccountButton from "./VerifyAccountButton";
import VerificationEmailRequestForm from "./VerificationEmailRequestForm";

// Shared surface styling (theme surface/border tokens), replacing this
// page's own hand-rolled Box with a plain border/shadow.
import Card from "../../ui/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/AuthLayout";

const VerifyAccountPage: React.FC = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();

    const token = searchParams.get("token") || "";
    const email = searchParams.get("email") || "";

    const handleSuccessRedirect = () => {
        navigate("/login", { replace: true });
    };

    return (
        <AuthLayout variant="status">
            {/* Same card width/padding/heading scale as every other auth
                page (Login, Signup, Forgot/Reset Password). */}
            <Card w="450px" maxW="md" p={{ base: 5, md: 7 }} textAlign="center">
                <Heading size="xl" color="brand.fg" mb={2}>
                    Verify Your Account
                </Heading>

                <Text fontSize="md" color="fg.muted" mb={6}>
                    Click the button below to verify your account and activate access.
                </Text>

                <Stack
                    align="center"
                    gap={6}
                    separator={<StackSeparator borderColor="border.default" />}
                >
                    <VerifyAccountButton
                        token={token}
                        email={email}
                        onSuccess={handleSuccessRedirect}
                    />

                    <VStack w="full" gap={3}>
                        <Text fontSize="md" color="fg.muted">
                            Link expired or already used?
                        </Text>
                        <VerificationEmailRequestForm initialEmail={email} />
                    </VStack>
                </Stack>
            </Card>
        </AuthLayout>
    );
};

export default VerifyAccountPage;