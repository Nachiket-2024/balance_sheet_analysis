import React from "react";
import { Box, Flex, IconButton, Text } from "@chakra-ui/react";

import { useAuthStore } from "../store/authStore";
import { useLanguageStore } from "../store/languageStore";
import translations from "../translations/translations";
import LogoutButton from "../auth/logout/LogoutButton";
import ThemeToggle from "./ThemeToggle";
import LanguageToggle from "./LanguageToggle";
import { ICON_BUTTON_PROPS } from "../ui/styles/buttonStyles";

interface NavbarProps {
    onToggleSidebar: () => void;
    /**
     * App-supplied content (buttons, icons, links, ...) rendered in the top
     * bar's action cluster, to the left of ThemeToggle/LogoutButton. Unlike
     * Sidebar's `extraItems` (a declarative link list, since sidebar entries
     * are all "the same shape"), the top bar's own built-ins are each
     * bespoke components, so this is a free-form ReactNode slot rather than
     * a typed item array: pass whatever you'd render anywhere else. See
     * AppLayout's own docstring and
     * docs/mystic_auth/template-usage/overview.md#shared-chrome-extension-points.
     * Optional and defaults to none, so existing callers see no change.
     */
    extraContent?: React.ReactNode;
}

/**
 * Top bar shown alongside Sidebar. Hosts the mobile menu toggle (hidden on
 * md+, where Sidebar is always visible), the caller's own name, and the
 * existing LogoutButton container (unchanged, already owns its own
 * mutation/navigation logic).
 */
const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar, extraContent }) => {
    // Chrome (this navbar, plus Sidebar) always renders in chromeLanguage,
    // not the page-wide translation language: it's English by default and stays
    // English even in the "en+hi"/"en+mr" mixed modes, only switching along
    // with the rest of the app for the plain "hi"/"mr" modes. See
    // store/languageStore.ts's LanguageMode docstring.
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    const t = translations.getFixedT(chromeLanguage, "layout");
    const name = useAuthStore((s) => s.name);

    return (
        <Flex
            as="header"
            align="center"
            justify="space-between"
            px={{ base: 4, md: 6 }}
            h="16"
            flexShrink={0}
            bg="bg.surface"
            borderBottom="1px solid"
            borderColor="border.default"
            position="sticky"
            top={0}
            zIndex="sticky"
        >
            <Flex align="center" gap={3}>
                <IconButton
                    aria-label={t("toggleNavigationMenu")}
                    onClick={onToggleSidebar}
                    display={{ base: "inline-flex", md: "none" }}
                    size="sm"
                    {...ICON_BUTTON_PROPS}
                >
                    ☰
                </IconButton>
                {name && (
                    <Box>
                        <Text fontSize="15px" color="fg.muted">
                            {t("signedInAs")} <Text as="span" fontWeight="semibold" color="fg.default">{name}</Text>
                        </Text>
                    </Box>
                )}
            </Flex>

            <Flex align="center" gap={3}>
                {extraContent}
                <LanguageToggle />
                <ThemeToggle />
                <LogoutButton />
            </Flex>
        </Flex>
    );
};

export default Navbar;
