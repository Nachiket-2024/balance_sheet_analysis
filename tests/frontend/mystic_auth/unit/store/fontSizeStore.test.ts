import { beforeEach, describe, expect, it } from 'vitest';

import { FONT_SIZES, useFontSizeStore } from '@/store/fontSizeStore';

describe('font size store', () => {
  beforeEach(() => {
    localStorage.clear();
    useFontSizeStore.setState({ fontSize: 'medium' });
    document.documentElement.style.fontSize = '';
  });

  it('persists a selected size and applies its root percentage', () => {
    useFontSizeStore.getState().setFontSize('large');

    expect(localStorage.getItem('font-size')).toBe('large');
    expect(document.documentElement.style.fontSize).toBe('112.5%');
    expect(useFontSizeStore.getState().fontSize).toBe('large');
  });

  it('clamps increase and decrease at the supported size boundaries', () => {
    expect(FONT_SIZES).toEqual(['small', 'medium', 'large']);
    useFontSizeStore.getState().decreaseFontSize();
    expect(useFontSizeStore.getState().fontSize).toBe('small');
    useFontSizeStore.getState().decreaseFontSize();
    expect(useFontSizeStore.getState().fontSize).toBe('small');
    useFontSizeStore.getState().increaseFontSize();
    useFontSizeStore.getState().increaseFontSize();
    useFontSizeStore.getState().increaseFontSize();
    expect(useFontSizeStore.getState().fontSize).toBe('large');
  });
});
