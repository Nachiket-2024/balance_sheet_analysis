import { create } from "zustand";

import translations, { SUPPORTED_LANGUAGES, type SupportedLanguage } from "../translations/translations";

/**
 * A "mode" is what the user actually picks from LanguageToggle. The plain
 * ones (en/hi/mr) mean "everything, including the navbar/sidebar, in this
 * language" - unchanged from before language mixing existed. The "en+hi"/
 * "en+mr" modes are the mixed ones: navbar/sidebar chrome stays English
 * while the rest of the app (page titles, forms, tables, messages) renders
 * in the paired language. See resolveLanguages() below for how each mode
 * maps to a (chrome, page) language pair.
 */
export const LANGUAGE_MODES = ["en", "hi", "mr", "gu", "en+hi", "en+mr", "en+gu"] as const;
export type LanguageMode = (typeof LANGUAGE_MODES)[number];

export const LANGUAGE_MODE_LABELS: Record<LanguageMode, string> = {
    en: "English",
    hi: "हिंदी (Hindi)",
    mr: "मराठी (Marathi)",
    gu: "ગુજરાતી (Gujarati)",
    "en+hi": "English + हिंदी",
    "en+mr": "English + मराठी",
    "en+gu": "English + ગુજરાતી",
};

interface ResolvedLanguages {
    /** Drives Navbar/Sidebar only, via translations.getFixedT - see those files. */
    chromeLanguage: SupportedLanguage;
    /** Drives every other component's useTranslation() (the global translation language). */
    pageLanguage: SupportedLanguage;
}

function resolveLanguages(mode: LanguageMode): ResolvedLanguages {
    switch (mode) {
        case "en":
            return { chromeLanguage: "en", pageLanguage: "en" };
        case "hi":
            return { chromeLanguage: "hi", pageLanguage: "hi" };
        case "mr":
            return { chromeLanguage: "mr", pageLanguage: "mr" };
        case "gu":
            return { chromeLanguage: "gu", pageLanguage: "gu" };
        case "en+hi":
            return { chromeLanguage: "en", pageLanguage: "hi" };
        case "en+mr":
            return { chromeLanguage: "en", pageLanguage: "mr" };
        case "en+gu":
            return { chromeLanguage: "en", pageLanguage: "gu" };
    }
}

interface LanguageState extends ResolvedLanguages {
    mode: LanguageMode;
    setMode: (mode: LanguageMode) => void;
}

const STORAGE_KEY = "language";

function isLanguageMode(value: string | null): value is LanguageMode {
    return value !== null && (LANGUAGE_MODES as readonly string[]).includes(value);
}

function getInitialMode(): LanguageMode {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLanguageMode(stored)) return stored;
    // No stored preference yet: respect the browser's language once, on
    // first visit only (never overrides an explicit later choice, since any
    // toggle immediately writes to storage above). Only plain modes are
    // derivable from a browser locale - there's no browser signal for "I
    // want the mixed English+Hindi chrome/page split", that's opt-in only.
    const browserLang = window.navigator.language.slice(0, 2);
    if ((SUPPORTED_LANGUAGES as readonly string[]).includes(browserLang)) {
        return browserLang as SupportedLanguage;
    }
    return "en";
}

function applyMode(mode: LanguageMode): void {
    const { pageLanguage } = resolveLanguages(mode);
    void translations.changeLanguage(pageLanguage);
    document.documentElement.lang = pageLanguage;
}

// Apply immediately at module load. This module is imported eagerly at the
// very top of main.tsx specifically so this runs before the first paint,
// avoiding a flash of the wrong language on reload (mirrors themeStore.ts).
const initialMode = getInitialMode();
applyMode(initialMode);

/**
 * Client-side UI preference (not server state), so it lives in Zustand
 * alongside authStore/themeStore rather than TanStack Query.
 */
export const useLanguageStore = create<LanguageState>((set) => ({
    mode: initialMode,
    ...resolveLanguages(initialMode),

    setMode: (mode) => {
        window.localStorage.setItem(STORAGE_KEY, mode);
        applyMode(mode);
        set({ mode, ...resolveLanguages(mode) });
    },
}));
