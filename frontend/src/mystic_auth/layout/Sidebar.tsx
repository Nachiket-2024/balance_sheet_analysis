import React, { useState } from "react";
import { Box, Stack, Text } from "@chakra-ui/react";
import { Link, NavLink } from "react-router";

import { IfCan } from "../authorization/IfCan";
import { NAV_ITEMS, type NavItem } from "./navItems";
import { APP_NAME } from "../core/settings";
import { useThemeStore } from "../store/themeStore";
import { useLanguageStore } from "../store/languageStore";
import translations from "../translations/translations";

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

interface SidebarNavLinkProps {
    to: string;
    onClick: () => void;
    label: string;
}

/**
 * Single nav entry. Needs its own hover flag (rather than a plain CSS
 * `:hover` rule) because NavLink's `style` prop only takes a function of
 * `{ isActive }` - there's no `isHovered` Chakra pseudo-prop equivalent
 * available here without introducing a stylesheet, so hover is tracked the
 * same way `isActive` already drives color/background below.
 */
const SidebarNavLink: React.FC<SidebarNavLinkProps> = ({ to, onClick, label }) => {
    const [isHovered, setIsHovered] = useState(false);
    const isDark = useThemeStore((s) => s.colorMode === "dark");

    // Raw brand scale steps (not the brand.subtle/selected semantic tokens)
    // - those are shared with StatTile/StyledSelect, and at their
    // light-mode values (brand.50/100) both read as barely-there against
    // the sidebar's white bg.surface (see system.ts's own comment on
    // brand.selected re: brand.50 being "barely-there" for this exact kind
    // of use). One step further along the scale each, in whichever
    // direction is "more visible" for the current mode, so hover/active are
    // both actually visible without touching the shared tokens' other
    // consumers. NavLink's style prop can't consume Chakra's _dark
    // condition (that's CSS-selector-based, this is inline styles), hence
    // reading colorMode directly instead.
    // Dark mode's scale runs the opposite direction from light's: a lower
    // number is brighter/more prominent against a dark surface, so hover
    // (less emphasis than active) takes the higher, closer-to-background
    // number - same brand.900/800 pairing system.ts's own subtle/selected
    // tokens already use for exactly this reason.
    const hoverBg = isDark ? "var(--chakra-colors-brand-900)" : "var(--chakra-colors-brand-100)";
    const activeBg = isDark ? "var(--chakra-colors-brand-800)" : "var(--chakra-colors-brand-200)";

    return (
        <NavLink
            to={to}
            onClick={onClick}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            style={({ isActive }) => ({
                display: "block",
                padding: "8px 12px",
                borderRadius: "6px",
                fontWeight: isActive ? 600 : 500,
                color: isActive ? "var(--chakra-colors-brand-fg)" : "var(--chakra-colors-fg-default)",
                background: isActive ? activeBg : isHovered ? hoverBg : "transparent",
                // Fast, snappy feedback rather than Chakra's default ~200ms
                // recipe transition, which reads as sluggish for something
                // as immediate as a hover response.
                transition: "background-color 0.1s ease",
            })}
        >
            {label}
        </NavLink>
    );
};

/**
 * Primary app navigation. Permanently visible on md+ screens; on smaller
 * screens it's an off-canvas panel toggled by Navbar's menu button (slides
 * in via transform so it stays in the DOM, avoiding remounting nav state).
 * Each permission-gated link is wrapped in IfCan so a caller who lacks that
 * permission never sees it; the route itself is still independently
 * enforced by ProtectedRoute.
 */
const Sidebar: React.FC<SidebarProps> = ({ isOpen, onNavigate, extraItems }) => {
    // Chrome (this sidebar, plus Navbar) always renders in chromeLanguage,
    // not the page-wide translation language - see Navbar.tsx's matching comment
    // and store/languageStore.ts's LanguageMode docstring.
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    const t = translations.getFixedT(chromeLanguage, "layout");
    // Built-in items pass a "namespace:key" translation key (see NavItem's
    // own docstring in navItems.ts); app-supplied extraItems pass a plain
    // display string instead, which exists() reliably tells apart since a
    // literal label is never itself a registered translation key.
    const resolveLabel = (label: string): string => (translations.exists(label, { lng: chromeLanguage }) ? t(label) : label);
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
            aria-label={t("mainNavigation")}
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
                        <SidebarNavLink key={item.to} to={item.to} onClick={onNavigate} label={resolveLabel(item.label)} />
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
