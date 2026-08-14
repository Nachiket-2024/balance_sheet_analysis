import React from "react";
import { Box, Flex, HStack, Heading, Text } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import { APP_NAME } from "../core/settings";
import ThemeToggle from "./ThemeToggle";
import LanguageToggle from "./LanguageToggle";

interface AuthLayoutProps {
    children: React.ReactNode;
    /**
     * "form" (default): vertically + horizontally centered, for login/signup/
     * reset-password style forms.
     * "status": horizontally centered but top-aligned with fixed top spacing,
     * for verification/confirmation/status pages whose content height varies.
     */
    variant?: "form" | "status";
}

/**
 * Shared shell for unauthenticated pages: centered branding header with a right-aligned theme
 * toggle, centered (or top-aligned, for the "status" variant) content area, and a shared footer.
 */
const AuthLayout: React.FC<AuthLayoutProps> = ({ children, variant = "form" }) => {
    const { t } = useTranslation("layout");

    return (
        <Flex
            direction="column"
            minH="100vh"
            bg="bg.canvas"
        >
            <Flex
                position="relative"
                align="center"
                justify="center"
                px={6}
                py={3}
                bg="brand.subtle"
                borderBottom="1px solid"
                borderColor="border.default"
            >
                <Flex
                    direction="column"
                    align="center"
                    textAlign="center"
                >
                    <Heading
                        as="h1"
                        size="2xl"
                        color="brand.fg"
                        letterSpacing="tight"
                    >
                        {APP_NAME}
                    </Heading>

                    <Text
                        fontSize="sm"
                        color="fg.muted"
                    >
                        {t("tagline")}
                    </Text>
                </Flex>

                <Box position="absolute" right={6}>
                    <HStack gap={3}>
                        <LanguageToggle />
                        <ThemeToggle />
                    </HStack>
                </Box>
            </Flex>

            {/* Main content: kept tight (not a large py) so the header,
                card, and footer all fit a normal laptop viewport without
                scrolling; centered vertically within whatever room remains
                via flex="1" + justify="center" rather than fixed padding */}
            <Flex
                flex="1"
                direction="column"
                align="center"
                justify={variant === "status" ? "flex-start" : "center"}
                pt={variant === "status" ? { base: 10, md: 16 } : 4}
                pb={4}
                px={4}
            >
                {children}
            </Flex>

            {/* Footer: same soft brand surface as the header, so the page
                reads as bookended by one consistent identity band rather
                than a branded top and a plain default-background bottom */}
            <Box
                as="footer"
                py={3}
                px={4}
                textAlign="center"
                bg="brand.subtle"
                borderTop="1px solid"
                borderColor="border.default"
            >
                <Text fontSize="xs" color="fg.muted">
                    &copy; {new Date().getFullYear()}{" "}
                    <Text as="span" color="brand.fg" fontWeight="medium">
                        {APP_NAME}
                    </Text>
                    {" "}{t("allRightsReserved")}
                </Text>
            </Box>
        </Flex>
    );
};

export default AuthLayout;