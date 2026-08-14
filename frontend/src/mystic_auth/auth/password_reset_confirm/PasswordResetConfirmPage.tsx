import React from "react";
import { Stack, Heading, Text, StackSeparator } from "@chakra-ui/react";
import { Link, useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";

import PasswordResetConfirmForm from "./PasswordResetConfirmForm";

// Shared surface styling (theme surface/border tokens): replaces this
// page's own hand-rolled bg="white"/boxShadow="lg" card.
import Card from "../../ui/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/AuthLayout";

const PasswordResetConfirmPage: React.FC = () => {
    const { t } = useTranslation("auth");
    const [searchParams] = useSearchParams();
    const token = searchParams.get("token") || "";

    const hasTokenFromUrl = !!token;

    return (
        <AuthLayout>
            <Card w="450px" maxW="md" p={{ base: 5, md: 7 }}>
                <Stack align="center" textAlign="center" separator={<StackSeparator />}>
                    <Heading size="xl" color="brand.fg">
                        {t("passwordResetConfirmPage.heading")}
                    </Heading>

                    {hasTokenFromUrl ? (
                        <Text fontSize="md" color="fg.muted">
                            {t("passwordResetConfirmPage.withToken")}
                        </Text>
                    ) : (
                        <Text fontSize="md" color="fg.muted">
                            {t("passwordResetConfirmPage.withoutToken")}
                        </Text>
                    )}

                    <PasswordResetConfirmForm token={token} />

                    <Text fontSize="16px" color="fg.muted">
                        {t("passwordResetConfirmPage.rememberPassword")}{" "}
                        <Link to="/login" style={{ color: "var(--chakra-colors-brand-fg)", fontWeight: 600 }}>
                            {t("passwordResetConfirmPage.backToLogin")}
                        </Link>
                    </Text>
                </Stack>
            </Card>
        </AuthLayout>
    );
};

export default PasswordResetConfirmPage;
