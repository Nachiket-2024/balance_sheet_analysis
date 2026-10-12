import { describe, it, expect } from 'vitest';

import {
  timeRangeToApiParams,
  isTimeRangeActive,
  timeRangeLabel,
  DEFAULT_TIME_RANGE_STATE,
} from '@/audit_log/auditLogListConfig';

// A fixed "now" so every assertion below is deterministic regardless of when the suite runs.
const NOW_MS = Date.parse('2026-01-15T12:00:00.000Z');

describe('timeRangeToApiParams', () => {
  it('resolves a preset to a `from`/`to` bound spanning exactly that many days, ending now', () => {
    const { from, to, days } = timeRangeToApiParams({ range: '7', customFrom: '', customTo: '' }, NOW_MS);
    expect(days).toBe(7);
    expect(to).toBe(new Date(NOW_MS).toISOString());
    // from = local midnight of the day 6 days before now (7 days inclusive of today) - setHours
    // resolves in the runner's own timezone, so the expectation is built the same way rather
    // than a hardcoded UTC string (which would only pass in a UTC-local test environment).
    const expectedFrom = new Date(NOW_MS - 6 * 86400000);
    expectedFrom.setHours(0, 0, 0, 0);
    expect(from).toBe(expectedFrom.toISOString());
  });

  it('resolves a custom range to the start/end of each picked day, inclusive', () => {
    const { from, to, days } = timeRangeToApiParams(
      { range: 'custom', customFrom: '2026-01-01', customTo: '2026-01-03' },
      NOW_MS
    );
    expect(from).toBe(new Date('2026-01-01T00:00:00').toISOString());
    expect(to).toBe(new Date('2026-01-03T23:59:59.999').toISOString());
    expect(days).toBe(3);
  });

  it('clamps a custom range longer than 90 days to the login-trend endpoint\'s own bound', () => {
    const { days } = timeRangeToApiParams({ range: 'custom', customFrom: '2020-01-01', customTo: '2026-01-01' }, NOW_MS);
    expect(days).toBe(90);
  });

  it('falls back to the preset days (ignoring the incomplete custom dates) when range is "custom" but no dates are picked yet', () => {
    const { days } = timeRangeToApiParams({ range: 'custom', customFrom: '', customTo: '' }, NOW_MS);
    expect(days).toBe(14);
  });
});

describe('isTimeRangeActive', () => {
  it('is false for the untouched 14-day default', () => {
    expect(isTimeRangeActive(DEFAULT_TIME_RANGE_STATE)).toBe(false);
  });

  it('is true once a non-default preset is picked', () => {
    expect(isTimeRangeActive({ range: '30', customFrom: '', customTo: '' })).toBe(true);
  });

  it('is true only once both custom dates are picked, not mid-edit with just one', () => {
    expect(isTimeRangeActive({ range: 'custom', customFrom: '2026-01-01', customTo: '' })).toBe(false);
    expect(isTimeRangeActive({ range: 'custom', customFrom: '2026-01-01', customTo: '2026-01-02' })).toBe(true);
  });
});

describe('timeRangeLabel', () => {
  const t = (key: string, opts?: Record<string, unknown>) => {
    if (key === 'shared.timeRange.rangeText') return `${opts?.from} - ${opts?.to}`;
    const presets: Record<string, string> = {
      'shared.timeRange.preset_7': 'Last 7 days',
      'shared.timeRange.preset_14': 'Last 14 days',
      'shared.timeRange.preset_30': 'Last 30 days',
      'shared.timeRange.preset_90': 'Last 90 days',
    };
    return presets[key] ?? key;
  };

  it('labels a preset by its translated name', () => {
    expect(timeRangeLabel({ range: '30', customFrom: '', customTo: '' }, t)).toBe('Last 30 days');
  });

  it('labels a single-day custom range as just that day', () => {
    expect(timeRangeLabel({ range: 'custom', customFrom: '2026-01-01', customTo: '2026-01-01' }, t)).toBe('2026-01-01');
  });

  it('labels a multi-day custom range as "from - to"', () => {
    expect(timeRangeLabel({ range: 'custom', customFrom: '2026-01-01', customTo: '2026-01-07' }, t)).toBe(
      '2026-01-01 - 2026-01-07'
    );
  });
});
