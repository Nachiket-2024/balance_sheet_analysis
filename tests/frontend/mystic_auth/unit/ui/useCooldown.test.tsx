import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';

import { useCooldown } from '@/ui/hooks/useCooldown';

describe('useCooldown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts at 0 and is not counting down initially', () => {
    const { result } = renderHook(() => useCooldown());
    expect(result.current.cooldown).toBe(0);
  });

  it('startCooldown(seconds) sets the cooldown and ticks it down every second', () => {
    const { result } = renderHook(() => useCooldown());

    act(() => {
      result.current.startCooldown(3);
    });
    expect(result.current.cooldown).toBe(3);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.cooldown).toBe(2);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.cooldown).toBe(1);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.cooldown).toBe(0);
  });

  it('defaults to 60 seconds when called without an argument', () => {
    const { result } = renderHook(() => useCooldown());

    act(() => {
      result.current.startCooldown();
    });
    expect(result.current.cooldown).toBe(60);
  });

  it('stops ticking once it reaches 0 (interval is cleared)', () => {
    const { result } = renderHook(() => useCooldown());

    act(() => {
      result.current.startCooldown(1);
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.cooldown).toBe(0);

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.cooldown).toBe(0);
  });

  it('clears the interval on unmount without throwing', () => {
    const { result, unmount } = renderHook(() => useCooldown());

    act(() => {
      result.current.startCooldown(10);
    });

    unmount();

    act(() => {
      vi.advanceTimersByTime(5000);
    });
  });

  it('restarting the cooldown resets the displayed value immediately', () => {
    const { result } = renderHook(() => useCooldown());

    act(() => {
      result.current.startCooldown(5);
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.cooldown).toBe(4);

    act(() => {
      result.current.startCooldown(10);
    });
    expect(result.current.cooldown).toBe(10);
  });
});
