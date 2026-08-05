import { createSystem, defaultConfig } from "@chakra-ui/react";
import type { SystemConfig } from "@chakra-ui/react";

/**
 * Formalizes the palette the app was already using ad hoc (teal for primary actions, gray
 * neutrals, red/green feedback) into theme tokens, so components reference tokens instead of
 * repeating raw hex/scale values.
 */
const config: SystemConfig = {
    theme: {
        tokens: {
            colors: {
                brand: {
                    50: { value: "#e6fffa" },
                    100: { value: "#b2f5ea" },
                    200: { value: "#81e6d9" },
                    300: { value: "#4fd1c5" },
                    400: { value: "#38b2ac" },
                    500: { value: "#319795" },
                    600: { value: "#2c7a7b" },
                    700: { value: "#285e61" },
                    800: { value: "#234e52" },
                    900: { value: "#1d4044" },
                },
            },
        },
        semanticTokens: {
            colors: {
                // Primary brand action color (buttons, links, active states)
                brand: {
                    solid: { value: "{colors.brand.600}" },
                    contrast: { value: "white" },
                    // Dark-mode aware unlike `muted` below: brand.600 text stays
                    // legible on a light brand.50 surface, but on `subtle`'s dark
                    // brand.900 surface (or bg.canvas/bg.surface) it's too close in
                    // brightness to the background, so dark mode lightens it.
                    fg: { value: { _light: "{colors.brand.600}", _dark: "{colors.brand.300}" } },
                    muted: { value: "{colors.brand.100}" },
                    // Soft, low-emphasis brand surface, for large areas
                    // (header/footer bands) that need to read as "branded"
                    // without brand.solid's high-contrast weight. Dark-mode
                    // aware unlike `muted` above: a light teal-50 tint would
                    // read as a jarring light patch on an otherwise dark
                    // page, so dark mode uses a low-brightness brand-tinted
                    // surface instead of the same light tint.
                    subtle: { value: { _light: "{colors.brand.50}", _dark: "{colors.brand.900}" } },
                    // One step darker/lighter than `subtle` above: `subtle` is meant for
                    // large low-emphasis surfaces, but that same brand.50 tint read as
                    // barely-there when reused for the sidebar's active-link background in
                    // light mode. `selected` exists for small, must-be-noticed highlights
                    // (nav active state, list selection) where `subtle` is too pale.
                    selected: { value: { _light: "{colors.brand.100}", _dark: "{colors.brand.800}" } },
                    emphasized: { value: "{colors.brand.700}" },
                    focusRing: { value: "{colors.brand.500}" },
                },
                // Page/app surfaces
                "bg.canvas": { value: { _light: "{colors.gray.100}", _dark: "{colors.gray.900}" } },
                "bg.surface": { value: { _light: "white", _dark: "{colors.gray.800}" } },
                "border.default": { value: { _light: "{colors.gray.200}", _dark: "{colors.gray.700}" } },
                // Overrides Chakra's own global `border` token (used by Input/Textarea/Select's
                // outline variant, not just our own `border.default` above). Its stock dark value
                // is gray.800, identical to bg.surface's dark value, so every form field's border
                // was invisible against the card behind it. Same value as border.default above,
                // just under the key Chakra's built-in recipes actually consume.
                border: { value: { _light: "{colors.gray.200}", _dark: "{colors.gray.700}" } },
                // Text
                "fg.default": { value: { _light: "{colors.gray.700}", _dark: "{colors.gray.100}" } },
                "fg.muted": { value: { _light: "{colors.gray.500}", _dark: "{colors.gray.400}" } },
                "fg.error": { value: { _light: "{colors.red.600}", _dark: "{colors.red.400}" } },
                "fg.success": { value: { _light: "{colors.green.600}", _dark: "{colors.green.400}" } },
            },
        },
    },
};

/**
 * Merges `config` on top of Chakra's `defaultConfig` (rather than replacing it, which is what
 * passing a bare custom config to createSystem would do) so the app keeps every default
 * token/recipe and only overrides what's listed above.
 */
export const system = createSystem(defaultConfig, config);
