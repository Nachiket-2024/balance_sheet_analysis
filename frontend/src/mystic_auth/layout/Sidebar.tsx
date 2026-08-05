import React from "react";
import { Box, Stack, Text } from "@chakra-ui/react";
import { Link, NavLink } from "react-router";

import { IfCan } from "../authorization/IfCan";
import { NAV_ITEMS, type NavItem } from "./navItems";
import { APP_NAME } from "../core/settings";

interface SidebarProps {
    isOpen: boolean;
    onNavigate: () => void;
    /**
     * App-supplied links, merged with the built-in ones and sorted by
     * `order` (see NavItem: items without one sort last, in the order
     * given, which is why omitting `order` entirely still reproduces the
     * original append-only behavior). Same NavItem shape and same IfCan
     * gating as the built-ins, see AppLayout's own docstring and
     * docs/mystic_auth/template-usage/overview.md#shared-chrome-extension-points.
     * Optional and defaults to none, so existing callers see no change.
     */
    extraItems?: NavItem[];
}

/**
 * Primary app navigation. Permanently visible on md+ screens; on smaller
 * screens it's an off-canvas panel toggled by Navbar's menu button (slides
 * in via transform so it stays in the DOM, avoiding remounting nav state).
 * Each permission-gated link is wrapped in IfCan so a caller who lacks that
 * permission never sees it; the route itself is still independently
 * enforced by ProtectedRoute.
 */
const Sidebar: React.FC<SidebarProps> = ({ isOpen, onNavigate, extraItems }) => {
    // Array.prototype.sort is stable (guaranteed since ES2019), so two items
    // with the same order (or both missing one) keep their relative
    // position from the merged array rather than getting shuffled.
    // undefined - undefined would be NaN, not 0, which is why both sides
    // fall back to Infinity rather than comparing `order` directly.
    const items = extraItems && extraItems.length > 0
        ? [...NAV_ITEMS, ...extraItems].sort(
              (a, b) => (a.order ?? Infinity) - (b.order ?? Infinity)
          )
        : NAV_ITEMS;
    return (
        <Box
            as="nav"
            aria-label="Main navigation"
            position={{ base: "fixed", md: "sticky" }}
            top={0}
            left={0}
            h="100vh"
            w="240px"
            flexShrink={0}
            bg="bg.surface"
            borderRight="1px solid"
            borderColor="border.default"
            zIndex="overlay"
            transform={{ base: isOpen ? "translateX(0)" : "translateX(-100%)", md: "none" }}
            transition="transform 0.2s ease"
            display="flex"
            flexDirection="column"
        >
            {/* h="16" fixed (not py-driven) so this border-bottom lines up
                exactly with Navbar.tsx's own border-bottom - both are fixed
                to the same height for that reason, rather than relying on
                matching padding to coincidentally produce the same total
                height as Navbar's differently-sized content (icon button +
                name text) would. */}
            <Box
                h="16"
                px={6}
                display="flex"
                alignItems="center"
                borderBottom="1px solid"
                borderColor="border.default"
                flexShrink={0}
            >
                <Link to="/dashboard" onClick={onNavigate} style={{ textDecoration: "none" }}>
                    <Text fontWeight="bold" fontSize="22px" color="brand.fg">
                        {APP_NAME}
                    </Text>
                </Link>
            </Box>

            <Stack p={3} gap={1} data-testid="nav-links">
                {items.map((item) => {
                    const link = (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            onClick={onNavigate}
                            style={({ isActive }) => ({
                                display: "block",
                                padding: "8px 12px",
                                borderRadius: "6px",
                                fontWeight: isActive ? 600 : 500,
                                color: isActive ? "var(--chakra-colors-brand-fg)" : "var(--chakra-colors-fg-default)",
                                background: isActive ? "var(--chakra-colors-brand-selected)" : "transparent",
                            })}
                        >
                            {item.label}
                        </NavLink>
                    );

                    if (!item.permission) return link;

                    return (
                        <IfCan key={item.to} action={item.permission}>
                            {link}
                        </IfCan>
                    );
                })}
            </Stack>
        </Box>
    );
};

export default Sidebar;
