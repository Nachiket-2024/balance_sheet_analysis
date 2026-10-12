import { describe, it, expect } from 'vitest';
import { colord, extend } from 'colord';
import mixPlugin from 'colord/plugins/mix';

import {
  deriveCanvasFrom,
  deriveSidebar,
} from '@/theme/appearanceThemeOverrides';
import { generateBrandScale } from '@/theme/generateBrandScale';
import { BRAND_COLOR } from '@/core/settings';

extend([mixPlugin]);

describe('deriveCanvasFrom', () => {
  it('derives a muted tint (not the 100 step as-is) for the light-mode value', () => {
    const scale = generateBrandScale('#2563eb');

    // A plain scale['100'] carries the input hue's full saturation, which
    // read pink/salmon at the top of the page for several hues - see this
    // function's own comment. The muted formula (retuned to match
    // design/dashboard.html's approved mockup): re-derive hue/saturation
    // from scale['600'], rebuild at 45% of that saturation and L=95.
    const { h, s } = colord(scale['600']).toHsl();
    const expected = colord({ h, s: Math.min(100, s * 0.45), l: 95 }).toHex();
    const light = deriveCanvasFrom(scale).light;
    expect(light).toBe(expected);
    // .not.toBe() doesn't type-check here; see the ".not chaining" note in
    // docs/mystic_auth/testing/overview.md. `expected` was already asserted
    // equal to `light` above and computed independently from scale['100'],
    // so this is a positive check that they land on different hex values.
    expect(light === scale['100']).toBe(false);
  });

  it('blends gray.900 with the 900 step for the dark-mode value (not a flat brand.900 wash)', () => {
    const scale = generateBrandScale('#2563eb');

    // 75/25 blend of gray.900 with the 900 step, not a flat wash of either.
    const { dark } = deriveCanvasFrom(scale);
    const blended = colord('#18181b').mix(scale['900'], 0.25).toHex();
    expect(dark).toBe(blended);
  });
});

describe('deriveSidebar', () => {
  // Regression test for a real bug: an earlier formula blended toward a
  // stock generic gray.900 (#18181b, L=10), which floors every possible
  // blend output at least that light - it could never reach the design
  // canvas's actual chrome darkness (#160f0d, L=6.9) no matter the blend
  // weight, so Sidebar/Navbar rendered a visibly lighter, flatter dark-mode
  // background than the mockup at the app's own default brand color.
  it("comes within a few RGB values of design/dashboard.html's literal #fbf4f2/#160f0d at the app's actual default brand color", () => {
    const scale = generateBrandScale(BRAND_COLOR);
    const { light, dark } = deriveSidebar(scale);

    const closeEnough = (a: string, b: string, maxChannelDelta: number) => {
      const ca = colord(a).toRgb();
      const cb = colord(b).toRgb();
      return (
        Math.abs(ca.r - cb.r) <= maxChannelDelta &&
        Math.abs(ca.g - cb.g) <= maxChannelDelta &&
        Math.abs(ca.b - cb.b) <= maxChannelDelta
      );
    };

    expect(closeEnough(light, '#fbf4f2', 12)).toBe(true);
    expect(closeEnough(dark, '#160f0d', 6)).toBe(true);
  });

  it('still varies with the input brand color (stays brand-derived, not a fixed hex)', () => {
    const warm = deriveSidebar(generateBrandScale('#b5533c'));
    const cool = deriveSidebar(generateBrandScale('#2563eb'));

    expect(warm.dark).not.toBe(cool.dark);
    expect(warm.light).not.toBe(cool.light);
  });
});
