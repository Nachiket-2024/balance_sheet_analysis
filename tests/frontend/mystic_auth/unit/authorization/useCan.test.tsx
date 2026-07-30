import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

import { useAuthStore } from '@/store/authStore';
import { useCan, useAuthorized } from '@/authorization/useCan';

const initialAuthState = useAuthStore.getState();

function seed(permissions?: string[]) {
  useAuthStore.setState(initialAuthState, true);
  if (permissions) {
    useAuthStore.getState().setAuthenticated(true);
    useAuthStore.getState().setProfile({
      name: 'Test User', email: 'test@example.com', role: 'user', permissions, has_password: true,
    });
  }
}

describe('useCan', () => {
  beforeEach(() => {
    seed();
  });

  it('returns true when the action is held in the auth store', () => {
    seed(['users:update', 'documents:view']);
    const { result } = renderHook(() => useCan('users:update'));
    expect(result.current).toBe(true);
  });

  it('returns false when the action is not held in the auth store', () => {
    seed(['documents:view']);
    const { result } = renderHook(() => useCan('users:update'));
    expect(result.current).toBe(false);
  });

  it('handles no permissions at all gracefully (returns false, never throws/undefined)', () => {
    const { result } = renderHook(() => useCan('users:update')); // unauthenticated, permissions: []
    expect(result.current).toBe(false);
  });

  it('handles an empty permissions array gracefully', () => {
    seed([]);
    const { result } = renderHook(() => useCan('users:update'));
    expect(result.current).toBe(false);
  });

  it('accepts an optional resourceType argument without changing the result', () => {
    seed(['documents:view']);
    const { result: withResourceType } = renderHook(() => useCan('documents:view', 'documents'));
    const { result: withoutResourceType } = renderHook(() => useCan('documents:view'));
    expect(withResourceType.current).toBe(true);
    expect(withoutResourceType.current).toBe(true);
  });
});

describe('useAuthorized', () => {
  it('behaves identically to useCan for a single permission', () => {
    seed(['policies:read']);
    const { result: authorized } = renderHook(() => useAuthorized('policies:read'));
    const { result: denied } = renderHook(() => useAuthorized('policies:delete'));

    expect(authorized.current).toBe(true);
    expect(denied.current).toBe(false);
  });
});
