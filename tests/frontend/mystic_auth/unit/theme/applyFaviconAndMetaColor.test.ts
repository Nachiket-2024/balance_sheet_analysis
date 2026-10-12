import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getBrandIconDataUri } from '@/theme/brandIcon';

function setDom() {
  document.head.innerHTML =
    '<link rel="icon" href="/favicon.svg" /><meta name="theme-color" content="#b5533c" />';
}

async function importWithFaviconUrl(url: string | undefined) {
  vi.doMock('@/core/settings', () => ({
    APP_FAVICON_URL: url,
    BRAND_COLOR: '#b5533c',
  }));
  return import('@/theme/applyFaviconAndMetaColor');
}

describe('applyFaviconAndMetaColor', () => {
  beforeEach(() => {
    setDom();
  });

  afterEach(() => {
    vi.resetModules();
    vi.doUnmock('@/core/settings');
  });

  it('uses the generated brand-color icon when no favicon override is configured', async () => {
    const { applyFaviconAndMetaColor } = await importWithFaviconUrl(undefined);

    applyFaviconAndMetaColor('#2563eb');

    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    expect(link?.href).toBe(getBrandIconDataUri('#2563eb'));
  });

  it('prefers APP_FAVICON_URL over the generated brand-color icon', async () => {
    const { applyFaviconAndMetaColor } = await importWithFaviconUrl('/custom-favicon.png');

    applyFaviconAndMetaColor('#2563eb');

    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    expect(link?.href).toContain('/custom-favicon.png');
  });

  it('still updates the theme-color meta tag when APP_FAVICON_URL is set', async () => {
    const { applyFaviconAndMetaColor } = await importWithFaviconUrl('/custom-favicon.png');

    applyFaviconAndMetaColor('#2563eb');

    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    expect(meta?.content).toBe('#2563eb');
  });

  it('falls back to the default favicon when no color and no override are set', async () => {
    const { applyFaviconAndMetaColor } = await importWithFaviconUrl(undefined);

    applyFaviconAndMetaColor(null);

    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    expect(link?.href).toContain('/favicon.svg');
  });
});
