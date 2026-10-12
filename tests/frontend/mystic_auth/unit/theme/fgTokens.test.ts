import { describe, it, expect } from 'vitest';

import { contrastRatio } from '@/theme/generateBrandScale';

// fg-default/fg-muted (theme/tailwind.css) are a cooler, faintly blue-tinted
// slate rather than a neutral gray scale - see tailwind.css's own comment.
// This re-verifies the swap didn't quietly drop below WCAG AA's 4.5:1
// body-text minimum, the reason those values were picked in the first
// place. Values below are literal, checked against theme/tailwind.css's
// :root/.dark blocks directly rather than importing them (plain CSS, no JS
// export) - a future edit to either file should update both.
const FG_DEFAULT = { light: '#101828', dark: '#eef1f6' };
const FG_MUTED = { light: '#667085', dark: '#9aa4b2' };
const bgSurfaceLight = '#ffffff';
const bgSurfaceDark = '#12151c';
const WCAG_AA_NORMAL_TEXT = 4.5;

describe('fg-default / fg-muted contrast', () => {
  it('fg-default clears WCAG AA against bg-surface in both modes', () => {
    expect(contrastRatio(FG_DEFAULT.light, bgSurfaceLight)).toBeGreaterThanOrEqual(WCAG_AA_NORMAL_TEXT);
    expect(contrastRatio(FG_DEFAULT.dark, bgSurfaceDark)).toBeGreaterThanOrEqual(WCAG_AA_NORMAL_TEXT);
  });

  it('fg-muted clears WCAG AA against bg-surface in both modes', () => {
    expect(contrastRatio(FG_MUTED.light, bgSurfaceLight)).toBeGreaterThanOrEqual(WCAG_AA_NORMAL_TEXT);
    expect(contrastRatio(FG_MUTED.dark, bgSurfaceDark)).toBeGreaterThanOrEqual(WCAG_AA_NORMAL_TEXT);
  });
});
