import { describe, it, expect, beforeEach, vi } from 'vitest';

function setNavigatorOnLine(value: boolean) {
  Object.defineProperty(window.navigator, 'onLine', {
    configurable: true,
    value,
  });
}

describe('networkStatusStore', () => {
  beforeEach(() => {
    vi.resetModules();
    setNavigatorOnLine(true);
  });

  it('defaults to online when navigator.onLine is true at load', async () => {
    const { useNetworkStatusStore } = await import('@/store/networkStatusStore');

    expect(useNetworkStatusStore.getState().isOnline).toBe(true);
  });

  it('starts offline when navigator.onLine is false at load', async () => {
    setNavigatorOnLine(false);

    const { useNetworkStatusStore } = await import('@/store/networkStatusStore');

    expect(useNetworkStatusStore.getState().isOnline).toBe(false);
  });

  it('flips to offline when the browser fires an "offline" event', async () => {
    const { useNetworkStatusStore } = await import('@/store/networkStatusStore');
    expect(useNetworkStatusStore.getState().isOnline).toBe(true);

    window.dispatchEvent(new Event('offline'));

    expect(useNetworkStatusStore.getState().isOnline).toBe(false);
  });

  it('flips back to online when the browser fires an "online" event', async () => {
    setNavigatorOnLine(false);
    const { useNetworkStatusStore } = await import('@/store/networkStatusStore');
    expect(useNetworkStatusStore.getState().isOnline).toBe(false);

    window.dispatchEvent(new Event('online'));

    expect(useNetworkStatusStore.getState().isOnline).toBe(true);
  });
});
