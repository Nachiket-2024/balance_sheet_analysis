import React from "react";
import { Stack, Heading, Text, StackSeparator } from "@chakra-ui/react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";

import PasswordResetRequestForm from "./PasswordResetRequestForm";

// Shared surface styling (theme surface/border tokens), replacing this
// page's own hand-rolled bg="white"/boxShadow="lg" card.
import Card from "../../ui/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/AuthLayout";

const PasswordResetRequestPage: React.FC = () => {
    const { t } = useTranslation("auth");

    return (
        <AuthLayout>
            <Card w="450px" maxW="md" p={{ base: 5, md: 7 }}>
                <Stack align="center" textAlign="center" separator={<StackSeparator />}>
                    <Heading size="xl" color="brand.fg">
                        {t("passwordResetRequestPage.heading")}
                    </Heading>

                    <Text fontSize="md" color="fg.muted">
                        {t("passwordResetRequestPage.subtitle")}
                    </Text>

                    <PasswordResetRequestForm />

                    <Text fontSize="16px" color="fg.muted">
                        {t("passwordResetRequestPage.rememberPassword")}{" "}
                        <Link to="/login" style={{ color: "var(--chakra-colors-brand-fg)", fontWeight: 600 }}>
                            {t("passwordResetRequestPage.backToLogin")}
                        </Link>
                    </Text>
                </Stack>
            </Card>
        </AuthLayout>
    );
};

export default PasswordResetRequestPage;
