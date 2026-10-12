import { describe, it, expect } from 'vitest';

import { formatLongDate, formatRelativeTime } from '@/ui/dates/dateFormatters';

const NOW = new Date('2026-09-16T12:00:00Z').getTime();

function ago(seconds: number): string {
  return new Date(NOW - seconds * 1000).toISOString();
}

describe('formatLongDate', () => {
  // Local-time constructor, so the weekday doesn't depend on the test machine's timezone.
  const date = new Date(2026, 8, 16, 12, 0);

  it('puts the day before the month in English', () => {
    expect(formatLongDate(date, 'en')).toMatch(/^Wednesday,? 16 September 2026$/);
  });

  it('uses native digits and no ASCII digits for Hindi, Marathi, and Gujarati', () => {
    for (const language of ['hi', 'mr', 'gu'] as const) {
      const formatted = formatLongDate(date, language);
      expect(formatted).not.toMatch(/[0-9]/);
      expect(formatted.length).toBeGreaterThan(0);
    }
    expect(formatLongDate(date, 'hi')).toContain('१६');
    expect(formatLongDate(date, 'gu')).toContain('૧૬');
  });
});

describe('formatRelativeTime', () => {
  it('says "now" for anything under a minute', () => {
    expect(formatRelativeTime(ago(0), 'en', NOW)).toBe('now');
    expect(formatRelativeTime(ago(59), 'en', NOW)).toBe('now');
  });

  it('picks the largest whole unit', () => {
    expect(formatRelativeTime(ago(2 * 60), 'en', NOW)).toBe('2 minutes ago');
    expect(formatRelativeTime(ago(90 * 60), 'en', NOW)).toBe('1 hour ago');
    expect(formatRelativeTime(ago(3 * 24 * 60 * 60), 'en', NOW)).toBe('3 days ago');
    expect(formatRelativeTime(ago(14 * 24 * 60 * 60), 'en', NOW)).toBe('2 weeks ago');
    expect(formatRelativeTime(ago(400 * 24 * 60 * 60), 'en', NOW)).toBe('last year');
  });

  it('treats a timestamp slightly in the future (clock skew) as now', () => {
    expect(formatRelativeTime(new Date(NOW + 5000).toISOString(), 'en', NOW)).toBe('now');
  });

  it('uses native digits for Hindi, Marathi, and Gujarati', () => {
    expect(formatRelativeTime(ago(5 * 60), 'hi', NOW)).toMatch(/५/);
    expect(formatRelativeTime(ago(5 * 60), 'mr', NOW)).toMatch(/५/);
    expect(formatRelativeTime(ago(5 * 60), 'gu', NOW)).toMatch(/૫/);
    expect(formatRelativeTime(ago(5 * 60), 'hi', NOW)).not.toMatch(/[0-9]/);
  });
});
