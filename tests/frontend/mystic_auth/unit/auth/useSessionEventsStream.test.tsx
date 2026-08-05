import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

import { useAuthStore } from '@/store/authStore';
import { useSessionEventsStream } from '@/auth/useSessionEventsStream';
import { queryClient } from '@/core/queryClient';
import { CURRENT_USER_QUERY_KEY } from '@/auth/current_user/useCurrentUserQuery';
import { SESSIONS_QUERY_KEY } from '@/dashboard/manage_sessions/useSessionsQuery';

class MockEventSource {
  url: string;
  withCredentials: boolean;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = !!init?.withCredentials;
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- test mock tracks its own last-created instance
    lastInstance = this;
  }

  close(): void {
    this.closed = true;
  }
}

let lastInstance: MockEventSource | null = null;
const originalEventSource = globalThis.EventSource;
const initialAuthState = useAuthStore.getState();

describe('useSessionEventsStream', () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true);
    lastInstance = null;
    // @ts-expect-error - a minimal stand-in for this suite, not a full EventSource implementation
    globalThis.EventSource = MockEventSource;
  });

  afterEach(() => {
    globalThis.EventSource = originalEventSource;
  });

  it('does not open a connection while unauthenticated', () => {
    useAuthStore.getState().setAuthenticated(false);

    renderHook(() => useSessionEventsStream());

    expect(lastInstance).toBeNull();
  });

  it('opens a credentialed connection to /auth/session-events once authenticated', () => {
    useAuthStore.getState().setAuthenticated(true);

    renderHook(() => useSessionEventsStream());

    expect(lastInstance).toBeTruthy();
    expect(lastInstance!.url).toContain('/auth/session-events');
    expect(lastInstance!.withCredentials).toBe(true);
  });

  it('closes the connection on unmount', () => {
    useAuthStore.getState().setAuthenticated(true);
    const { unmount } = renderHook(() => useSessionEventsStream());

    unmount();

    expect(lastInstance!.closed).toBe(true);
  });

  it('invalidates the current-user and sessions queries when a push event arrives', () => {
    useAuthStore.getState().setAuthenticated(true);
    renderHook(() => useSessionEventsStream());
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    lastInstance!.onmessage?.({ data: '{"type":"revoked"}' } as MessageEvent);

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: CURRENT_USER_QUERY_KEY });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: SESSIONS_QUERY_KEY });

    invalidateSpy.mockRestore();
  });
});
