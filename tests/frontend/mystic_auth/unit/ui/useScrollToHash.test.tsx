import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { useScrollToHash } from '@/ui/hooks/useScrollToHash';

function wrapperFor(initialPath: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>;
  };
}

describe('useScrollToHash', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = '';
  });

  it('does nothing when there is no hash in the URL', () => {
    const scrollIntoView = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView;

    renderHook(() => useScrollToHash(), { wrapper: wrapperFor('/dashboard') });

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(scrollIntoView).toHaveBeenCalledTimes(0);
  });

  it('scrolls the target element into view once it is present', () => {
    const target = document.createElement('div');
    target.id = 'manage-sessions';
    document.body.appendChild(target);
    const scrollIntoView = vi.fn();
    target.scrollIntoView = scrollIntoView;

    renderHook(() => useScrollToHash(), {
      wrapper: wrapperFor('/dashboard#manage-sessions'),
    });

    act(() => {
      vi.advanceTimersByTime(0);
    });

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
  });

  it('retries until the element mounts, then scrolls it into view', () => {
    const scrollIntoView = vi.fn();

    renderHook(() => useScrollToHash(), { wrapper: wrapperFor('/dashboard#late-section') });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(scrollIntoView).toHaveBeenCalledTimes(0);

    const target = document.createElement('div');
    target.id = 'late-section';
    target.scrollIntoView = scrollIntoView;
    document.body.appendChild(target);

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
  });

  it('gives up after 20 retries when the element never appears', () => {
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');

    renderHook(() => useScrollToHash(), { wrapper: wrapperFor('/dashboard#never-appears') });

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(setTimeoutSpy).toHaveBeenCalledTimes(20);
  });

  it('decodes a URL-encoded hash before looking up the element id', () => {
    const target = document.createElement('div');
    target.id = 'a b';
    document.body.appendChild(target);
    const scrollIntoView = vi.fn();
    target.scrollIntoView = scrollIntoView;

    renderHook(() => useScrollToHash(), { wrapper: wrapperFor('/dashboard#a%20b') });

    act(() => {
      vi.advanceTimersByTime(0);
    });

    expect(scrollIntoView).toHaveBeenCalled();
  });

  it('stops retrying after unmount (cancelled flag prevents late scrollIntoView calls)', () => {
    const scrollIntoView = vi.fn();

    const { unmount } = renderHook(() => useScrollToHash(), {
      wrapper: wrapperFor('/dashboard#unmount-target'),
    });

    unmount();

    const target = document.createElement('div');
    target.id = 'unmount-target';
    target.scrollIntoView = scrollIntoView;
    document.body.appendChild(target);

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(scrollIntoView).toHaveBeenCalledTimes(0);
  });
});
