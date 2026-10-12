import { colord, extend } from "colord";
import a11yPlugin from "colord/plugins/a11y";

extend([a11yPlugin]);

export type BrandScaleStep = "50" | "100" | "200" | "300" | "400" | "500" | "600" | "700" | "800" | "900";
export type BrandScale = Record<BrandScaleStep, string>;

// Target lightness (%) per step, calibrated against the shipped amber scale
// (app/theme.ts's brand.50-900, Tailwind's amber scale) so an arbitrary
// input hue lands at roughly the same visual weight per step.
const LIGHTNESS_LADDER: Record<BrandScaleStep, number> = {
    "50": 96,
    "100": 90,
    "200": 80,
    "300": 70,
    "400": 60,
    "500": 50,
    "600": 44,
    "700": 37,
    "800": 31,
    "900": 25,
};

// Saturation stays close to the input color's own, tapered slightly at the
// darkest steps so they don't read as an oversaturated near-black.
const SATURATION_MULTIPLIER: Record<BrandScaleStep, number> = {
    "50": 1,
    "100": 1,
    "200": 1,
    "300": 1,
    "400": 1,
    "500": 0.97,
    "600": 1,
    "700": 0.95,
    "800": 0.88,
    "900": 0.8,
};

/**
 * Generates the app's 50-900 color scale from a single user-picked
 * hex: fixes hue (and roughly saturation), interpolates lightness across
 * LIGHTNESS_LADDER. Single source of truth for every brand-colored surface
 * (buttons, focus rings, canvas tint, logo badge, favicon).
 */
export function generateBrandScale(hex: string): BrandScale {
    const { h, s } = colord(hex).toHsl();
    const scale = {} as BrandScale;
    (Object.keys(LIGHTNESS_LADDER) as BrandScaleStep[]).forEach((step) => {
        scale[step] = colord({
            h,
            s: Math.min(100, s * SATURATION_MULTIPLIER[step]),
            l: LIGHTNESS_LADDER[step],
        }).toHex();
    });
    return scale;
}

/** WCAG contrast ratio between two colors (1-21). */
export function contrastRatio(a: string, b: string): number {
    return colord(a).contrast(b);
}
