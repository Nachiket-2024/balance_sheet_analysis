import { create } from "zustand";

export type ColorMode = "light" | "dark";

interface ThemeState {
    colorMode: ColorMode;
    toggleColorMode: () => void;
    setColorMode: (mode: ColorMode) => void;
}

const STORAGE_KEY = "color-mode";

function getInitialColorMode(): ColorMode {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
    // No stored preference yet, respect the OS/browser setting once, on
    // first visit only (never overrides an explicit later choice, since
    // any toggle immediately writes to storage above). Guarded: jsdom (the
    // test environment) doesn't implement matchMedia at all.
    if (typeof window.matchMedia !== "function") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Chakra v3's default `_dark`/`_light` style conditions resolve against a `.dark` class on an
 * ancestor element: there is no separate ColorModeProvider in v3 core to call instead, this
 * class toggle IS the mechanism.
 */
function applyColorModeClass(mode: ColorMode): void {
    document.documentElement.classList.toggle("dark", mode === "dark");
    document.documentElement.style.colorScheme = mode;
}

// Apply immediately at module load. This module is imported eagerly at the
// very top of main.tsx specifically so this runs before the first paint,
// avoiding a flash of the wrong theme on reload for a user who chose dark.
const initialColorMode = getInitialColorMode();
applyColorModeClass(initialColorMode);

/**
 * Client-side UI preference (not server state), so it lives in Zustand alongside authStore
 * rather than TanStack Query, matching this app's existing state-management split.
 */
export const useThemeStore = create<ThemeState>((set) => ({
    colorMode: initialColorMode,

    toggleColorMode: () =>
        set((state) => {
            const next: ColorMode = state.colorMode === "dark" ? "light" : "dark";
            window.localStorage.setItem(STORAGE_KEY, next);
            applyColorModeClass(next);
            return { colorMode: next };
        }),

    setColorMode: (mode) => {
        window.localStorage.setItem(STORAGE_KEY, mode);
        applyColorModeClass(mode);
        set({ colorMode: mode });
    },
}));
