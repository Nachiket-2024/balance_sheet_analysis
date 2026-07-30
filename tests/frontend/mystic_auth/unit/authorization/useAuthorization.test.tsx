import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, renderHook } from '@testing-library/react';

import { useAuthStore } from '@/store/authStore';
import { useAuthorization } from '@/authorization/useAuthorization';

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

describe('useAuthorization', () => {
  beforeEach(() => {
    seed();
  });

  it('exposes the profile/permissions currently held in the auth store', () => {
    seed(['users:read_own', 'documents:view']);
    const { result } = renderHook(() => useAuthorization());

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.name).toBe('Test User');
    expect(result.current.permissions).toEqual(['users:read_own', 'documents:view']);
  });

  it('can() returns true only for a held permission', () => {
    seed(['documents:view']);
    const { result } = renderHook(() => useAuthorization());

    expect(result.current.can('documents:view')).toBe(true);
    expect(result.current.can('documents:delete')).toBe(false);
  });

  it('can() ignores the optional resourceType argument (flat permission list has no resource-type dimension)', () => {
    seed(['documents:view']);
    const { result } = renderHook(() => useAuthorization());

    expect(result.current.can('documents:view', 'documents')).toBe(true);
    expect(result.current.can('documents:view', 'some_other_resource_type')).toBe(true);
  });

  it('can() fails closed (returns false) while unauthenticated / permissions empty', () => {
    const { result } = renderHook(() => useAuthorization()); // unauthenticated initial state

    expect(result.current.isAuthenticated).toBeNull();
    expect(result.current.can('documents:view')).toBe(false);
  });

  it('a real component can conditionally render off can()', () => {
    seed(['documents:view']);

    function Probe() {
      const { can } = useAuthorization();
      return <button disabled={!can('documents:view')}>View</button>;
    }

    render(<Probe />);

    expect(screen.getByRole('button', { name: 'View' })).toBeEnabled();
  });
});
