import { describe, it, expect } from 'vitest';

import { generateBrandScale, contrastRatio } from '@/theme/generateBrandScale';

describe('generateBrandScale', () => {
  it('generates all ten brand scale steps as hex colors', () => {
    const scale = generateBrandScale('#2563eb');

    expect(Object.keys(scale).sort()).toEqual(
      ['100', '200', '300', '400', '50', '500', '600', '700', '800', '900'].sort()
    );
    for (const value of Object.values(scale)) {
      expect(value).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it('gets lighter from 900 to 50 (lightness ladder is respected)', () => {
    const scale = generateBrandScale('#2563eb');

    // 50 is lightest, 900 darkest; sum of RGB channels as a rough luminance proxy.
    const luminance = (hex: string) => {
      const n = parseInt(hex.slice(1), 16);
      return ((n >> 16) & 0xff) + ((n >> 8) & 0xff) + (n & 0xff);
    };

    expect(luminance(scale['50'])).toBeGreaterThan(luminance(scale['500']));
    expect(luminance(scale['500'])).toBeGreaterThan(luminance(scale['900']));
  });

  it('caps saturation at 100 for an already-saturated input (no overflow crash)', () => {
    // No .not.toThrow() (see the ".not chaining" note in
    // docs/mystic_auth/testing/overview.md); an uncaught throw fails this test on its own.
    const scale = generateBrandScale('#ff0000');

    expect(scale['500']).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it('is deterministic for the same input', () => {
    expect(generateBrandScale('#16a34a')).toEqual(generateBrandScale('#16a34a'));
  });
});

describe('contrastRatio', () => {
  it('returns the maximum ratio (21) for black against white', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 0);
  });

  it('returns 1 for identical colors', () => {
    expect(contrastRatio('#2563eb', '#2563eb')).toBeCloseTo(1, 5);
  });
});
