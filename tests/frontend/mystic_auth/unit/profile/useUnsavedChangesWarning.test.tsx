import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

import { useUnsavedChangesWarning } from '@/profile/useUnsavedChangesWarning';

function dispatchBeforeUnload(): Event & { defaultPrevented: boolean } {
  const event = new Event('beforeunload', { cancelable: true }) as Event & { defaultPrevented: boolean };
  window.dispatchEvent(event);
  return event;
}

describe('useUnsavedChangesWarning', () => {
  it('does not intercept beforeunload when there are no unsaved changes', () => {
    renderHook(() => useUnsavedChangesWarning(false));

    const event = dispatchBeforeUnload();
    expect(event.defaultPrevented).toBe(false);
  });

  it('intercepts (preventDefault) beforeunload while isDirty is true', () => {
    renderHook(() => useUnsavedChangesWarning(true));

    const event = dispatchBeforeUnload();
    expect(event.defaultPrevented).toBe(true);
  });

  it('stops intercepting once isDirty flips back to false', () => {
    const { rerender } = renderHook(({ isDirty }) => useUnsavedChangesWarning(isDirty), {
      initialProps: { isDirty: true },
    });

    expect(dispatchBeforeUnload().defaultPrevented).toBe(true);

    rerender({ isDirty: false });

    expect(dispatchBeforeUnload().defaultPrevented).toBe(false);
  });

  it('removes its listener on unmount, so a stale dirty flag can no longer block navigation', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = renderHook(() => useUnsavedChangesWarning(true));

    unmount();

    expect(removeSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));
    expect(dispatchBeforeUnload().defaultPrevented).toBe(false);

    removeSpy.mockRestore();
  });
});
