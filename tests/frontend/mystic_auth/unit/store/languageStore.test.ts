import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('languageStore', () => {
  beforeEach(() => {
    vi.resetModules();
    window.localStorage.clear();
    document.documentElement.lang = '';
    Object.defineProperty(window.navigator, 'language', { value: 'en-US', configurable: true });
  });

  it('defaults to the "en" mode when there is no stored preference and the browser language is unsupported', async () => {
    const { useLanguageStore } = await import('@/store/languageStore');

    expect(useLanguageStore.getState().mode).toBe('en');
    expect(useLanguageStore.getState().chromeLanguage).toBe('en');
    expect(useLanguageStore.getState().pageLanguage).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('respects a stored mode and derives chrome/page languages from it on load', async () => {
    window.localStorage.setItem('language', 'hi');

    const { useLanguageStore } = await import('@/store/languageStore');

    expect(useLanguageStore.getState().mode).toBe('hi');
    expect(useLanguageStore.getState().chromeLanguage).toBe('hi');
    expect(useLanguageStore.getState().pageLanguage).toBe('hi');
    expect(document.documentElement.lang).toBe('hi');
  });

  it('falls back to the browser language once on first visit when nothing is stored', async () => {
    Object.defineProperty(window.navigator, 'language', { value: 'mr-IN', configurable: true });

    const { useLanguageStore } = await import('@/store/languageStore');

    expect(useLanguageStore.getState().mode).toBe('mr');
  });

  it('falls back to the browser language for Gujarati too, on first visit when nothing is stored', async () => {
    Object.defineProperty(window.navigator, 'language', { value: 'gu-IN', configurable: true });

    const { useLanguageStore } = await import('@/store/languageStore');

    expect(useLanguageStore.getState().mode).toBe('gu');
  });

  it('never derives a mixed mode from the browser language - only "en"/"hi"/"mr"/"gu" are auto-detected', async () => {
    Object.defineProperty(window.navigator, 'language', { value: 'fr-FR', configurable: true });

    const { useLanguageStore } = await import('@/store/languageStore');

    expect(useLanguageStore.getState().mode).toBe('en');
  });

  it.each([
    ['en', 'en', 'en'],
    ['hi', 'hi', 'hi'],
    ['mr', 'mr', 'mr'],
    ['gu', 'gu', 'gu'],
    ['en+hi', 'en', 'hi'],
    ['en+mr', 'en', 'mr'],
    ['en+gu', 'en', 'gu'],
  ] as const)(
    'setMode(%s) sets chromeLanguage=%s and pageLanguage=%s, keeping chrome English for mixed modes',
    async (mode, chromeLanguage, pageLanguage) => {
      const { useLanguageStore } = await import('@/store/languageStore');

      useLanguageStore.getState().setMode(mode);

      expect(useLanguageStore.getState().mode).toBe(mode);
      expect(useLanguageStore.getState().chromeLanguage).toBe(chromeLanguage);
      expect(useLanguageStore.getState().pageLanguage).toBe(pageLanguage);
      expect(window.localStorage.getItem('language')).toBe(mode);
      // The DOM lang attribute follows the page (majority-content)
      // language, not chrome - see languageStore.ts's applyMode().
      expect(document.documentElement.lang).toBe(pageLanguage);
    }
  );
});
