// Product name shown across the UI (navbar, auth pages, document title).
// Single source of truth so it only needs changing here.
export const APP_NAME = import.meta.env.VITE_APP_NAME;

// Optional logo (bundled asset, absolute path, or remote URL) shown instead of the
// plain-text APP_NAME wherever the brand mark renders (Sidebar, AuthLayout). Unset by
// default, so forks keep working with the text wordmark until VITE_APP_LOGO_URL is set.
export const APP_LOGO_URL = import.meta.env.VITE_APP_LOGO_URL || undefined;

// Optional browser tab favicon (bundled asset, absolute path, or remote URL). Kept
// separate from APP_LOGO_URL since a wide logo mark rarely scales down cleanly to a
// 16x16 tab icon. Unset by default, so the generated brand-color icon (brandIcon.ts)
// is used instead - see applyFaviconAndMetaColor.ts.
export const APP_FAVICON_URL = import.meta.env.VITE_APP_FAVICON_URL || undefined;

// Contact address shown on the Terms of Service / Privacy Policy pages. Unset by
// default, in which case those pages show a "replace this" placeholder instead of a
// blank or fabricated address.
export const SUPPORT_EMAIL = import.meta.env.VITE_SUPPORT_EMAIL || undefined;

// App-wide default brand color, fed into theme/generateBrandScale.ts to build the whole
// `brand` token scale (see theme/system.ts's buildSystem). Falls back to this app's
// terracotta so forks work with no .env changes; set VITE_BRAND_COLOR to re-skin the
// app from one place. A signed-in user's own Appearance pick still overrides this per-user.
export const BRAND_COLOR = import.meta.env.VITE_BRAND_COLOR || "#b5533c";

const settings = {
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
};

export default settings;