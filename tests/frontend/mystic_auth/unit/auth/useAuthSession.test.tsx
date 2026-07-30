import { describe, it, expect, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import { useAuthSession } from '@/auth/current_user/useCurrentUserQuery';

const mock = new MockAdapter(api);

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const initialAuthState = useAuthStore.getState();

describe('authStore: profile/permissions capture', () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true);
  });

  it('setProfile stores name/email/role/permissions', () => {
    useAuthStore.getState().setProfile({
      name: 'Test User',
      email: 'test@example.com',
      role: 'user',
      permissions: ['users:read_own', 'users:update_own'],
      has_password: true,
    });

    const state = useAuthStore.getState();
    expect(state.name).toBe('Test User');
    expect(state.email).toBe('test@example.com');
    expect(state.role).toBe('user');
    expect(state.permissions).toEqual(['users:read_own', 'users:update_own']);
  });

  it('setProfile defaults permissions to an empty array when omitted', () => {
    // @ts-expect-error - simulating a backend response that omits permissions
    useAuthStore.getState().setProfile({ name: 'Test User', email: 'test@example.com', role: 'user' });

    expect(useAuthStore.getState().permissions).toEqual([]);
  });

  it('setAuthenticated(false) clears a stale profile (e.g. from the 401 interceptor)', () => {
    useAuthStore.getState().setProfile({
      name: 'Test User', email: 'test@example.com', role: 'user', permissions: ['x:y'], has_password: true,
    });
    useAuthStore.getState().setAuthenticated(true);
    expect(useAuthStore.getState().permissions).toEqual(['x:y']);

    useAuthStore.getState().setAuthenticated(false);

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.permissions).toEqual([]);
  });

  it('setAuthenticated(true) does not touch the profile fields', () => {
    useAuthStore.getState().setAuthenticated(true);

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.name).toBeNull(); // untouched, not fabricated
  });

  it('reset() clears the profile along with the auth flags', () => {
    useAuthStore.getState().setProfile({
      name: 'Test User', email: 'test@example.com', role: 'user', permissions: ['x:y'], has_password: true,
    });
    useAuthStore.getState().setAuthenticated(true);

    useAuthStore.getState().reset();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBeNull();
    expect(state.name).toBeNull();
    expect(state.permissions).toEqual([]);
  });
});

describe('useAuthSession: syncs the currentUser query into the auth store', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('stores name/email/role/permissions and marks authenticated on a successful session check', async () => {
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'test@example.com',
      role: 'user',
      permissions: ['users:read_own', 'users:update_own'],
    });

    renderHook(() => useAuthSession(), { wrapper });

    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(true));

    const state = useAuthStore.getState();
    expect(state.name).toBe('Test User');
    expect(state.email).toBe('test@example.com');
    expect(state.permissions).toEqual(['users:read_own', 'users:update_own']);
  });

  it('clears the profile and marks unauthenticated on a failed session check (401)', async () => {
    mock.onGet('/auth/me').reply(401, { detail: 'Not authenticated' });

    renderHook(() => useAuthSession(), { wrapper });

    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(false));

    const state = useAuthStore.getState();
    expect(state.name).toBeNull();
    expect(state.permissions).toEqual([]);
  });
});
