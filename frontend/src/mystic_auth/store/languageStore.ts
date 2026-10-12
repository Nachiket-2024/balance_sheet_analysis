import { create } from "zustand";

import translations, { loadLanguage, SUPPORTED_LANGUAGES, type SupportedLanguage } from "../translations/translations";

// A "mode" is what the user picks from LanguageToggle. The plain ones (en/hi/mr) mean
// everything, including navbar/sidebar, in that language. The "en+hi"/"en+mr" modes
// are mixed: navbar/sidebar chrome stays English while the rest of the app renders in
// the paired language. See resolveLanguages() below for how each mode maps to a
// (chrome, page) language pair.
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
    languageRevision: number;
    setMode: (mode: LanguageMode) => void;
}

const STORAGE_KEY = "language";

function isLanguageMode(value: string | null): value is LanguageMode {
    return value !== null && (LANGUAGE_MODES as readonly string[]).includes(value);
}

function getInitialMode(): LanguageMode {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLanguageMode(stored)) return stored;
    // No stored preference yet: respect the browser's language once, on first visit
    // only (any toggle immediately writes to storage above, so this never overrides
    // an explicit choice). Only plain modes are derivable from a browser locale; the
    // mixed chrome/page split is opt-in only.
    const browserLang = window.navigator.language.slice(0, 2);
    if ((SUPPORTED_LANGUAGES as readonly string[]).includes(browserLang)) {
        return browserLang as SupportedLanguage;
    }
    return "en";
}

let languageLoadVersion = 0;
let refreshLanguageState = () => {};

function applyMode(mode: LanguageMode): void {
    const { pageLanguage } = resolveLanguages(mode);
    document.documentElement.lang = pageLanguage;
    const version = ++languageLoadVersion;
    void loadLanguage(pageLanguage).then(() => {
        if (version === languageLoadVersion) {
            void translations.changeLanguage(pageLanguage).then(refreshLanguageState);
        }
    });
}

// Apply immediately at module load, imported eagerly at the top of main.tsx so this
// runs before first paint, avoiding a flash of the wrong language (mirrors themeStore.ts).
const initialMode = getInitialMode();

// Client-side preference, not server state, so it lives in Zustand alongside
// authStore/themeStore rather than TanStack Query.
export const useLanguageStore = create<LanguageState>((set) => ({
    mode: initialMode,
    languageRevision: 0,
    ...resolveLanguages(initialMode),

    setMode: (mode) => {
        window.localStorage.setItem(STORAGE_KEY, mode);
        applyMode(mode);
        set({ mode, ...resolveLanguages(mode) });
    },
}));

refreshLanguageState = () => {
    useLanguageStore.setState((state) => ({ languageRevision: state.languageRevision + 1 }));
};

applyMode(initialMode);
