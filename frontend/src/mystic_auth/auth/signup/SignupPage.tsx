import React from "react";
import { Stack, Heading, Text } from "@chakra-ui/react";

import SignupForm from "./SignupForm";

// Shared surface styling (theme surface/border tokens), replacing this
// page's own hand-rolled bg="white"/boxShadow="lg" card.
import Card from "../../ui/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/AuthLayout";

const SignupPage: React.FC = () => {
    return (
        <AuthLayout>
            {/* Wider than the other auth cards since the form itself is
                genuinely wider (name + email side by side), but the same
                padding/spacing scale as every other auth page for visual
                consistency. */}
            <Card w="1000px" maxW="800px" p={{ base: 5, md: 7 }}>
                <Stack textAlign="center" gap={3}>
                    <Heading size="2xl" color="brand.fg">
                        Create your account
                    </Heading>
                    <Text fontSize="md" color="fg.muted">
                        Get started in less than a minute
                    </Text>

                    <SignupForm />
                </Stack>
            </Card>
        </AuthLayout>
    );
};

export default SignupPage;
