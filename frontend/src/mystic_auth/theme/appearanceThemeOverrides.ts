import { colord, extend } from "colord";
import mixPlugin from "colord/plugins/mix";

import { generateBrandScale } from "./generateBrandScale";

extend([mixPlugin]);

// A stock neutral gray.900. Dark mode's canvasFrom is blended against this
// rather than a flat brand step.
const GRAY_900 = "#18181b";

// This app's own dark canvas value from tailwind.css, not GRAY_900 -
// deriveSidebar blends toward this instead (see its own comment for why):
// GRAY_900 (#18181b, L=10) floors every possible blend result at least
// that light, which can never reach the mockup's actual chrome darkness
// (L=6.9) no matter the blend weight.
const BG_CANVAS_DARK = "#0b0d12";

/** The bg.canvasFrom pair for an arbitrary brand scale - shared with
 * AppearanceCard.tsx's preview boxes so they show exactly what applying
 * the pick will render. Retuned to match the "neutral surfaces plus brand
 * accent" system from design/dashboard.html's approved mockup: that page's
 * body background is a *very* faint radial brand tint (rgba(brand-500,
 * .07) light / .14 dark over an otherwise neutral canvas), not a visibly
 * colored wash. L=95 (up from an earlier L=90/92) is what actually gets
 * there - at very high lightness a color reads as barely-there regardless
 * of its raw saturation number, so this keeps `scale["600"]`'s hue/sat
 * mostly intact (only trimmed to 45%) rather than desaturating it, the
 * mistake an earlier pass made (assuming "muted" meant "less saturated"
 * when it actually meant "much lighter"). Dark value: blends gray.900 with
 * the 900 step at a light 25% weight - enough to keep a hint of brand cast,
 * not enough to read as a colored panel. */
export function deriveCanvasFrom(scale: ReturnType<typeof generateBrandScale>): { light: string; dark: string } {
    const { h, s } = colord(scale["600"]).toHsl();
    return {
        light: colord({ h, s: Math.min(100, s * 0.45), l: 95 }).toHex(),
        dark: colord(GRAY_900).mix(scale["900"], 0.25).toHex(),
    };
}

/** The bg.sidebar pair (Sidebar.tsx/Navbar.tsx's own surface, distinct from
 * bg.surface/bg.canvas, and from bg.canvasFrom's gradient tint) for an
 * arbitrary brand scale. Retuned to match design/dashboard.html's approved
 * mockup: its sidebar/navbar "chrome" color (--bg-chrome, #fbf4f2 light /
 * #160f0d dark) sits so close to the page's own canvas color that the two
 * are barely distinguishable - a whisper of brand hue, not a visibly
 * tinted panel. Measuring that mockup color directly: L=96.7/S=53% light,
 * L=6.9/S=26% dark - both nearly the *same lightness as bg.canvas itself*
 * (L=97 light, L=6 dark). A lower lightness (L=88) with a 0.45-weight dark
 * blend reads as a distinctly warm/rose panel next to the white cards in
 * front of it, visibly "tinted" rather than barely-there - so this keeps
 * `scale["600"]`'s saturation mostly intact (a trimmed 85%, since high
 * lightness already mutes it) but pushes lightness up to L=96.5 - just one
 * notch below bg.canvas, enough to read as its own surface without
 * becoming a colored block. Dark mixes BG_CANVAS_DARK (this app's own
 * bg.canvas dark value, not GRAY_900, which floors every blend at L=10,
 * too light to ever reach the mockup's L=6.9 no matter the weight) with a
 * deep, near-black step at 60% weight - tuned
 * so the *default* brand color's output lands within a couple RGB values of
 * the mockup's literal #160f0d, while staying a real brand-derived blend
 * for any other brand color a fork picks. */
export function deriveSidebar(scale: ReturnType<typeof generateBrandScale>): { light: string; dark: string } {
    const { h, s } = colord(scale["600"]).toHsl();
    const deepStep = colord({ h, s, l: 7 });
    return {
        light: colord({ h, s: Math.min(100, s * 0.85), l: 96.5 }).toHex(),
        dark: colord(BG_CANVAS_DARK).mix(deepStep, 0.6).toHex(),
    };
}
