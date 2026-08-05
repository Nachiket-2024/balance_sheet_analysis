import { describe, it, expect } from 'vitest';

import { parseUserAgent } from '@/dashboard/manage_sessions/parseUserAgent';

describe('parseUserAgent', () => {
  it('returns "Unknown device" for a null user agent', () => {
    expect(parseUserAgent(null)).toBe('Unknown device');
  });

  it('returns "Unknown device" for an empty string', () => {
    expect(parseUserAgent('')).toBe('Unknown device');
  });

  it('labels an unrecognized user agent as unknown browser and OS', () => {
    expect(parseUserAgent('SomeCustomClient/1.0')).toBe('Unknown browser on Unknown OS');
  });

  it('identifies Chrome on Windows', () => {
    const ua =
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
    expect(parseUserAgent(ua)).toBe('Chrome on Windows');
  });

  it('identifies Firefox on Windows', () => {
    const ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0';
    expect(parseUserAgent(ua)).toBe('Firefox on Windows');
  });

  it('identifies Safari on macOS, not Chrome, even though the UA also lists "like Gecko"', () => {
    const ua =
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15';
    expect(parseUserAgent(ua)).toBe('Safari on macOS');
  });

  it('identifies Safari on iOS from an iPhone UA', () => {
    const ua =
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
    expect(parseUserAgent(ua)).toBe('Safari on iOS');
  });

  it('identifies Chrome on Android', () => {
    const ua =
      'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';
    expect(parseUserAgent(ua)).toBe('Chrome on Android');
  });

  it('identifies Edge as Edge, not Chrome, even though its UA also contains "Chrome" and "Safari"', () => {
    const ua =
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0';
    expect(parseUserAgent(ua)).toBe('Edge on Windows');
  });

  it('identifies Opera as Opera, not Chrome, even though its UA also contains "Chrome" and "Safari"', () => {
    const ua =
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0';
    expect(parseUserAgent(ua)).toBe('Opera on Windows');
  });

  it('identifies Linux when no other OS pattern matches', () => {
    const ua = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
    expect(parseUserAgent(ua)).toBe('Chrome on Linux');
  });

  it('recognizes a known browser even when the OS is unrecognized', () => {
    const ua = 'Mozilla/5.0 (SomeExoticOS) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
    expect(parseUserAgent(ua)).toBe('Chrome on Unknown OS');
  });
});
