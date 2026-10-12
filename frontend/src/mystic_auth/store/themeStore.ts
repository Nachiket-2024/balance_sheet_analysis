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
    // No stored preference yet: respect the OS/browser setting once, on first visit
    // only (any toggle immediately writes to storage above, so this never overrides
    // an explicit choice). Guarded since jsdom doesn't implement matchMedia.
    if (typeof window.matchMedia !== "function") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// Tailwind's dark-mode selectors resolve against the `.dark` class on the
// document root, so this is the color-mode mechanism.
function applyColorModeClass(mode: ColorMode): void {
    document.documentElement.classList.toggle("dark", mode === "dark");
    document.documentElement.style.colorScheme = mode;
}

// Apply immediately at module load, imported eagerly at the top of main.tsx so this
// runs before first paint, avoiding a flash of the wrong theme for a user who chose dark.
const initialColorMode = getInitialColorMode();
applyColorModeClass(initialColorMode);

// Client-side preference, not server state, so it lives in Zustand alongside authStore
// rather than TanStack Query.
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
