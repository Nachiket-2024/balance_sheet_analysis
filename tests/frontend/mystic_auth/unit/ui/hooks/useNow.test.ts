import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useNow } from '@/ui/hooks/useNow';

describe('useNow', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts from the current clock value', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-09T00:00:00.000Z'));

    const { result } = renderHook(() => useNow(30_000));

    expect(result.current).toBe(new Date('2026-10-09T00:00:00.000Z').getTime());
  });

  it('refreshes on the configured interval', () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000);
    const { result } = renderHook(() => useNow(30_000));

    act(() => {
      vi.advanceTimersByTime(30_000);
    });

    expect(result.current).toBe(31_000);
  });

  it('cleans up the interval when the hook unmounts', () => {
    vi.useFakeTimers();
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    const { unmount } = renderHook(() => useNow(30_000));

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalledTimes(1);
  });
});
