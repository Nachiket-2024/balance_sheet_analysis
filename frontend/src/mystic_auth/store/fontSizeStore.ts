import { create } from "zustand";

export type FontSize = "small" | "medium" | "large";

export const FONT_SIZES: FontSize[] = ["small", "medium", "large"];

// Percent of the browser's default font size, not a fixed px value, so a visitor who
// already bumped their browser/OS text size for accessibility gets it scaled rather
// than overridden.
const FONT_SIZE_PERCENT: Record<FontSize, string> = {
    small: "87.5%",
    medium: "100%",
    large: "112.5%",
};

interface FontSizeState {
    fontSize: FontSize;
    increaseFontSize: () => void;
    decreaseFontSize: () => void;
    setFontSize: (size: FontSize) => void;
}

const STORAGE_KEY = "font-size";

function getInitialFontSize(): FontSize {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "small" || stored === "medium" || stored === "large") return stored;
    return "medium";
}

// Scales the root <html> font-size, which the UI's rem-based sizing is relative
// to, instead of overriding components one by one. One root-level switch
// resizes the whole UI, same approach themeStore.ts uses for the `.dark` class.
function applyFontSize(size: FontSize): void {
    document.documentElement.style.fontSize = FONT_SIZE_PERCENT[size];
}

// Apply immediately at module load (same as themeStore.ts): this module is imported
// eagerly at the top of main.tsx so the persisted size applies before first paint.
const initialFontSize = getInitialFontSize();
applyFontSize(initialFontSize);

// Client-side preference, not server state, so it lives in Zustand alongside
// themeStore/languageStore rather than TanStack Query.
export const useFontSizeStore = create<FontSizeState>((set, get) => ({
    fontSize: initialFontSize,

    setFontSize: (size) => {
        window.localStorage.setItem(STORAGE_KEY, size);
        applyFontSize(size);
        set({ fontSize: size });
    },

    increaseFontSize: () => {
        const idx = FONT_SIZES.indexOf(get().fontSize);
        get().setFontSize(FONT_SIZES[Math.min(idx + 1, FONT_SIZES.length - 1)]);
    },

    decreaseFontSize: () => {
        const idx = FONT_SIZES.indexOf(get().fontSize);
        get().setFontSize(FONT_SIZES[Math.max(idx - 1, 0)]);
    },
}));
