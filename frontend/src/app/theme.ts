export interface AppThemeOverrides {
    /** A hand-picked brand hex, overriding VITE_BRAND_COLOR at build time
     * without editing env/mystic_auth/.env.dev. theme/applyBrandCssVars.ts runs
     * this through the same generateBrandScale.ts 50-900 ladder a signed-in
     * user's own Appearance pick uses, so it's still just one hex, not a
     * hand-authored scale. */
    brandColor?: string;
    /** Any other theme/tailwind.css custom property to override outright
     * (fonts, radii, a hand-authored token that doesn't fit
     * generateBrandScale's lightness ladder), applied once at startup.
     * Doesn't take a light/dark pair: for a token that differs by mode
     * (like the brand-derived --bg-canvas-from/--bg-sidebar), override
     * generateBrandScale.ts's formula instead - a single literal here would
     * apply to both modes. */
    cssVars?: Record<string, string>;
}

/**
 * App-owned theme overrides (see docs/mystic_auth/template-usage/overview.md).
 *
 * For the common case, just changing the brand color, you don't need this
 * file: set VITE_BRAND_COLOR (env/mystic_auth/.env.dev's BRAND_COLOR, aliased
 * like APP_NAME) to any hex and rebuild. See
 * docs/mystic_auth/template-usage/overview.md#environment-configuration.
 *
 * This file is for anything beyond that single color. Counterpart to
 * app_sdk.ts: theme/applyBrandCssVars.ts and theme/tailwind.css are
 * upstream-owned, so hand-editing them directly would conflict on every
 * `scripts/mystic_auth/upstream-sync/sync-upstream.sh` sync. This file's
 * `cssVars` gets applied on top of them instead - the same "yours, upstream
 * never touches it again" pattern app_sdk.ts uses. A signed-in user's own
 * Appearance pick still overrides `brandColor` client-side for that user
 * only.
 *
 * Ships empty in every release, so it never conflicts on a sync.
 *
 * Example:
 *
 * const overrides: AppThemeOverrides = {
 *     brandColor: "#4338ca",
 *     cssVars: { "--radius-control": "0.25rem" },
 * };
 */
const overrides: AppThemeOverrides = {};

export default overrides;
