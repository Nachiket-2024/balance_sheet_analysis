import React from "react";
import { IconButton } from "@chakra-ui/react";

import { useThemeStore } from "../store/themeStore";

/**
 * Light/dark mode switch, backed by store/themeStore.ts (persists to
 * localStorage, toggles the `.dark` class Chakra's own _dark/_light style
 * conditions key off, see that store's own docstring for why there's no
 * separate ColorModeProvider in Chakra v3 to reach for instead).
 */
const ThemeToggle: React.FC = () => {
    const colorMode = useThemeStore((s) => s.colorMode);
    const toggleColorMode = useThemeStore((s) => s.toggleColorMode);
    const isDark = colorMode === "dark";

    return (
        <IconButton
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
            onClick={toggleColorMode}
            variant="ghost"
            size="sm"
        >
            {isDark ? "☀️" : "🌙"}
        </IconButton>
    );
};

export default ThemeToggle;
