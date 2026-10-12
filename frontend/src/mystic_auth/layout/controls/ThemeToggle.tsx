import React from "react";
import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useThemeStore } from "../../store/themeStore";
import { Button } from "../../ui/buttons/Button";

// Rotate+cross-fade timing for the Sun/Moon swap, from the same
// duration-hover/easing-hover tokens FAST_HOVER_TRANSITION uses.
const ICON_SWAP_TRANSITION = "opacity var(--duration-hover) var(--easing-hover), transform var(--duration-hover) var(--easing-hover)";

/**
 * Light/dark mode switch, backed by store/themeStore.ts (persists to
 * localStorage and toggles the `.dark` class consumed by Tailwind's dark-mode
 * selectors; no provider is required.
 */
const ThemeToggle: React.FC = () => {
    const { t } = useTranslation("layout");
    const colorMode = useThemeStore((s) => s.colorMode);
    const toggleColorMode = useThemeStore((s) => s.toggleColorMode);
    const isDark = colorMode === "dark";

    return (
        <Button
            aria-label={isDark ? t("switchToLightMode") : t("switchToDarkMode")}
            onClick={toggleColorMode}
            variant="icon"
            size="icon-sm"
        >
            {/* Both icons always render, stacked in the same spot - only
                opacity/rotation swap on colorMode change, so the toggle
                animates between them. Neither is permanently tinted; color
                still inherits the button's own currentColor/hover treatment. */}
            <div className="relative w-4 h-4 flex items-center justify-center">
                <Sun
                    size={16}
                    aria-hidden="true"
                    style={{
                        position: "absolute",
                        transition: ICON_SWAP_TRANSITION,
                        opacity: isDark ? 1 : 0,
                        transform: isDark ? "rotate(0deg) scale(1)" : "rotate(-90deg) scale(0.5)",
                    }}
                />
                <Moon
                    size={16}
                    aria-hidden="true"
                    style={{
                        position: "absolute",
                        transition: ICON_SWAP_TRANSITION,
                        opacity: isDark ? 0 : 1,
                        transform: isDark ? "rotate(90deg) scale(0.5)" : "rotate(0deg) scale(1)",
                    }}
                />
            </div>
        </Button>
    );
};

export default ThemeToggle;
