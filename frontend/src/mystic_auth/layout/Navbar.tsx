import React from "react";
import { Box, Flex, IconButton, Text } from "@chakra-ui/react";

import { useAuthStore } from "../store/authStore";
import LogoutButton from "../auth/logout/LogoutButton";
import ThemeToggle from "./ThemeToggle";
import { ICON_BUTTON_PROPS } from "../ui/styles/buttonStyles";

interface NavbarProps {
    onToggleSidebar: () => void;
}

/**
 * Top bar shown alongside Sidebar. Hosts the mobile menu toggle (hidden on
 * md+, where Sidebar is always visible), the caller's own name, and the
 * existing LogoutButton container (unchanged, already owns its own
 * mutation/navigation logic).
 */
const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar }) => {
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
                    aria-label="Toggle navigation menu"
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
                            Signed in as <Text as="span" fontWeight="semibold" color="fg.default">{name}</Text>
                        </Text>
                    </Box>
                )}
            </Flex>

            <Flex align="center" gap={3}>
                <ThemeToggle />
                <LogoutButton />
            </Flex>
        </Flex>
    );
};

export default Navbar;
