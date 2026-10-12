import { create } from "zustand";

import { applyFaviconAndMetaColor } from "../theme/applyFaviconAndMetaColor";

interface AppearanceState {
    /** null = using the app default scale (app/theme.ts). */
    brandColor: string | null;
    /** Applies immediately (favicon/meta + localStorage cache). The brand scale and
     * background CSS react automatically since AppearanceThemeProvider.tsx subscribes
     * to this store directly. See AppearanceCard.tsx for the save step, and
     * useCurrentUserQuery.ts's useAuthSession for applying the server's value. */
    setBrandColor: (hex: string | null) => void;
}

const BRAND_KEY = "brand-color";

function readCached(key: string): string | null {
    return window.localStorage.getItem(key);
}

function writeCached(key: string, hex: string | null): void {
    if (hex) window.localStorage.setItem(key, hex);
    else window.localStorage.removeItem(key);
}

const initialBrandColor = readCached(BRAND_KEY);

// Applied immediately at module load, before first paint (same reasoning as
// themeStore.ts), but scoped to just the favicon/meta tag: the brand scale and
// background are applied separately by applyBrandCssVars.ts. This is only the
// locally cached guess;
// useAuthSession reconciles it against the server value once GET /auth/me resolves.
applyFaviconAndMetaColor(initialBrandColor);

// Client-side preference cache, not server state, same Zustand + localStorage split
// this app uses for color mode, font size, and language.
export const useAppearanceStore = create<AppearanceState>((set) => ({
    brandColor: initialBrandColor,

    setBrandColor: (hex) => {
        writeCached(BRAND_KEY, hex);
        applyFaviconAndMetaColor(hex);
        set({ brandColor: hex });
    },
}));
