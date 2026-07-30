import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('themeStore', () => {
  beforeEach(() => {
    vi.resetModules();
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
    document.documentElement.style.colorScheme = '';
    // jsdom doesn't implement matchMedia by default; restore that baseline.
    // @ts-expect-error - deleting to restore the jsdom default
    delete window.matchMedia;
  });

  it('defaults to light when there is no stored preference and matchMedia is unavailable (jsdom)', async () => {
    const { useThemeStore } = await import('@/store/themeStore');

    expect(useThemeStore.getState().colorMode).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('respects a stored "dark" preference and applies the dark class on load', async () => {
    window.localStorage.setItem('color-mode', 'dark');

    const { useThemeStore } = await import('@/store/themeStore');

    expect(useThemeStore.getState().colorMode).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('falls back to the OS preference via matchMedia when nothing is stored', async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;

    const { useThemeStore } = await import('@/store/themeStore');

    expect(useThemeStore.getState().colorMode).toBe('dark');
  });

  it('toggleColorMode flips the mode, persists it, and updates the DOM class', async () => {
    const { useThemeStore } = await import('@/store/themeStore');
    expect(useThemeStore.getState().colorMode).toBe('light');

    useThemeStore.getState().toggleColorMode();

    expect(useThemeStore.getState().colorMode).toBe('dark');
    expect(window.localStorage.getItem('color-mode')).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    useThemeStore.getState().toggleColorMode();

    expect(useThemeStore.getState().colorMode).toBe('light');
    expect(window.localStorage.getItem('color-mode')).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('setColorMode sets an explicit mode and persists it', async () => {
    const { useThemeStore } = await import('@/store/themeStore');

    useThemeStore.getState().setColorMode('dark');

    expect(useThemeStore.getState().colorMode).toBe('dark');
    expect(window.localStorage.getItem('color-mode')).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });
});
