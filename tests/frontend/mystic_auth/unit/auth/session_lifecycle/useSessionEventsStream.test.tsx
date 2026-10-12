import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

import { useAuthStore } from '@/store/authStore';
import { useSessionEventsStream } from '@/auth/session_lifecycle/useSessionEventsStream';
import { queryClient } from '@/core/queryClient';
import { CURRENT_USER_QUERY_KEY } from '@/auth/current_user/useCurrentUserQuery';
import { SESSIONS_QUERY_KEY } from '@/active_sessions/useSessionsQuery';
import {
  markSelfPermissionMutation,
  resetSelfPermissionMutationGuardForTests,
} from '@/auth/session_lifecycle/selfPermissionMutationGuard';

class MockEventSource {
  url: string;
  withCredentials: boolean;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = !!init?.withCredentials;
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- tracks the last-created instance
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
    resetSelfPermissionMutationGuardForTests();
    // @ts-expect-error - minimal EventSource stand-in for this suite
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

  it('resets the entire query cache (not just invalidate) on a permissions_changed event', () => {
    useAuthStore.getState().setAuthenticated(true);
    renderHook(() => useSessionEventsStream());
    const resetSpy = vi.spyOn(queryClient, 'resetQueries');
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    lastInstance!.onmessage?.({ data: '{"type":"permissions_changed"}' } as MessageEvent);

    // resetQueries (not invalidateQueries): drops cached data outright, so a
    // permission-gated page using placeholderData: keepPreviousData (e.g.
    // RateLimitsPage) has no stale data left to show after access is revoked.
    expect(resetSpy).toHaveBeenCalledWith();
    expect(invalidateSpy.mock.calls.length).toBe(0);

    resetSpy.mockRestore();
    invalidateSpy.mockRestore();
  });

  it('drops every held permission synchronously, before any refetch resolves, on a permissions_changed event', () => {
    useAuthStore.setState({ isAuthenticated: true, permissions: ['rate_limits:read', 'users:list_all'] });
    renderHook(() => useSessionEventsStream());
    // Never resolves: proves the drop happens synchronously, not after resetQueries' refetch.
    vi.spyOn(queryClient, 'resetQueries').mockReturnValue(new Promise(() => {}));

    lastInstance!.onmessage?.({ data: '{"type":"permissions_changed"}' } as MessageEvent);

    expect(useAuthStore.getState().permissions).toEqual([]);
  });

  it('skips the synchronous drop for the echo of this tab\'s own self-targeted mutation', () => {
    useAuthStore.setState({ isAuthenticated: true, permissions: ['rate_limits:read', 'users:list_all'] });
    renderHook(() => useSessionEventsStream());
    vi.spyOn(queryClient, 'resetQueries').mockReturnValue(new Promise(() => {}));
    markSelfPermissionMutation();

    lastInstance!.onmessage?.({ data: '{"type":"permissions_changed"}' } as MessageEvent);

    expect(useAuthStore.getState().permissions).toEqual(['rate_limits:read', 'users:list_all']);
  });

  it('does not skip a SECOND permissions_changed event within the same window - only one echo is ever swallowed per self-mutation', () => {
    // Guards against a plain time-windowed skip: a genuine revoke landing
    // right after this tab's own mutation must still fail closed, not be
    // mistaken for the same echo twice.
    useAuthStore.setState({ isAuthenticated: true, permissions: ['rate_limits:read', 'users:list_all'] });
    renderHook(() => useSessionEventsStream());
    vi.spyOn(queryClient, 'resetQueries').mockReturnValue(new Promise(() => {}));
    markSelfPermissionMutation();

    // First event: treated as this tab's own echo, drop skipped.
    lastInstance!.onmessage?.({ data: '{"type":"permissions_changed"}' } as MessageEvent);
    expect(useAuthStore.getState().permissions).toEqual(['rate_limits:read', 'users:list_all']);

    // Second event, same window: treated as a genuine change, fails closed.
    lastInstance!.onmessage?.({ data: '{"type":"permissions_changed"}' } as MessageEvent);
    expect(useAuthStore.getState().permissions).toEqual([]);
  });
});
