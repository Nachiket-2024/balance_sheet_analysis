import { describe, it, expect, beforeEach, beforeAll } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import { setupAuthInterceptor } from '@/auth/session_lifecycle/setupAuthInterceptor';
import { queryClient } from '@/core/queryClient';
import { useCurrentUserQuery } from '@/auth/current_user/useCurrentUserQuery';
import {
  trackSessionRotatingRequest,
  resetSessionRotationGuardForTests,
} from '@/auth/session_lifecycle/sessionRotationGuard';

const mock = new MockAdapter(api);

describe('setupAuthInterceptor', () => {
  beforeAll(() => {
    setupAuthInterceptor();
  });

  beforeEach(() => {
    mock.reset();
    resetSessionRotationGuardForTests();
    useAuthStore.getState().setAuthenticated(true);
    useAuthStore.getState().setProfile({
      name: 'Test User', email: 'test@example.com', role: 'user', permissions: ['documents:view'], has_password: true,
      created_at: '2026-01-15T00:00:00Z', active_sessions: 1,
    });
  });

  it('marks the session unauthenticated (and clears the profile) on a 401 when silent refresh also fails', async () => {
    mock.onGet('/some/protected/resource').reply(401, { detail: 'Not authenticated' });
    mock.onPost('/auth/refresh/').reply(401, { detail: 'Invalid or revoked refresh token' });

    await expect(api.get('/some/protected/resource')).rejects.toMatchObject({ response: { status: 401 } });

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.permissions).toEqual([]);
  });

  it('silently refreshes and retries once on a 401 from an eligible endpoint, never marking the session unauthenticated', async () => {
    let refreshCalls = 0;
    mock.onPost('/auth/refresh/').reply(() => {
      refreshCalls += 1;
      return [200, { message: 'Tokens refreshed successfully' }];
    });

    let getCalls = 0;
    mock.onGet('/auth/me').reply(() => {
      getCalls += 1;
      // First attempt 401s (expired access token); the retry after refresh succeeds.
      return getCalls === 1 ? [401, { detail: 'Not authenticated' }] : [200, { email: 'test@example.com' }];
    });

    const res = await api.get('/auth/me');

    expect(res.data).toEqual({ email: 'test@example.com' });
    expect(refreshCalls).toBe(1);
    expect(getCalls).toBe(2);
    // The session was salvaged : never flagged unauthenticated at any point.
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('does not attempt a silent refresh for a 401 on excluded auth endpoints (e.g. login)', async () => {
    const refreshMock = mock.onPost('/auth/refresh/').reply(200, { message: 'Tokens refreshed successfully' });
    mock.onPost('/auth/login').reply(401, { detail: 'Invalid credentials' });

    await expect(
      api.post('/auth/login', { email: 'test@example.com', password: 'wrong' })
    ).rejects.toMatchObject({ response: { status: 401 } });

    expect(mock.history.post.filter((req) => req.url === '/auth/refresh/')).toHaveLength(0);
    void refreshMock;
  });

  it('coordinates concurrent 401s behind a single in-flight refresh call', async () => {
    let refreshCalls = 0;
    mock.onPost('/auth/refresh/').reply(() => {
      refreshCalls += 1;
      return [200, { message: 'Tokens refreshed successfully' }];
    });

    let getCalls = 0;
    mock.onGet('/auth/me').reply(() => {
      getCalls += 1;
      return getCalls <= 2 ? [401, { detail: 'Not authenticated' }] : [200, { email: 'test@example.com' }];
    });

    const [first, second] = await Promise.all([api.get('/auth/me'), api.get('/auth/me')]);

    expect(first.status).toBe(200);
    expect(second.status).toBe(200);
    // Two concurrent 401s must share one refresh call, not trigger two.
    expect(refreshCalls).toBe(1);
  });

  it('waits out an in-flight session-rotating request instead of expiring a request that loses ' +
    'the race against it (e.g. a query refetch racing the account-settings password change)', async () => {
    let refreshCalls = 0;
    mock.onPost('/auth/refresh/').reply(() => {
      refreshCalls += 1;
      // First refresh attempt: the old refresh cookie, momentarily stale
      // because the rotating request's fresh cookies haven't landed yet.
      // Second attempt (after the rotation settles): the new cookie works.
      return refreshCalls === 1
        ? [401, { detail: 'Invalid or revoked refresh token' }]
        : [200, { message: 'Tokens refreshed successfully' }];
    });

    let policiesCalls = 0;
    mock.onGet('/policies/mine').reply(() => {
      policiesCalls += 1;
      return policiesCalls === 1 ? [401, { detail: 'Not authenticated' }] : [200, { policies: [] }];
    });

    // Simulates the password-change mutation: still in flight when the
    // racing request above hits its first (failed) refresh attempt, and
    // resolves shortly after.
    let resolveRotation: () => void = () => {};
    const rotation = new Promise<void>((resolve) => {
      resolveRotation = resolve;
    });
    trackSessionRotatingRequest(rotation);

    const racingRequest = api.get('/policies/mine');
    // Let the racing request's first refresh attempt run and fail before the
    // rotating request settles, to actually exercise the race.
    await new Promise((resolve) => setTimeout(resolve, 10));
    resolveRotation();

    const res = await racingRequest;

    expect(res.data).toEqual({ policies: [] });
    expect(refreshCalls).toBe(2);
    expect(policiesCalls).toBe(2);
    // Salvaged via the rotation-aware retry : never flagged unauthenticated.
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('still expires a session that stays dead after the in-flight rotation settles (a real ' +
    'logout/deactivation, not just a lost race)', async () => {
    mock.onPost('/auth/refresh/').reply(401, { detail: 'Invalid or revoked refresh token' });
    mock.onGet('/policies/mine').reply(401, { detail: 'Not authenticated' });

    let resolveRotation: () => void = () => {};
    const rotation = new Promise<void>((resolve) => {
      resolveRotation = resolve;
    });
    trackSessionRotatingRequest(rotation);

    const racingRequest = api.get('/policies/mine');
    await new Promise((resolve) => setTimeout(resolve, 10));
    resolveRotation();

    await expect(racingRequest).rejects.toMatchObject({ response: { status: 401 } });

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('does NOT touch auth state on a 403 : the session is still valid, just missing a permission', async () => {
    mock.onGet('/some/admin/resource').reply(403, { detail: 'Forbidden' });

    await expect(api.get('/some/admin/resource')).rejects.toMatchObject({ response: { status: 403 } });

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.permissions).toEqual(['documents:view']);
  });

  it('leaves auth state untouched on other errors (e.g. 500) and still rejects the promise', async () => {
    mock.onGet('/some/resource').reply(500);

    await expect(api.get('/some/resource')).rejects.toMatchObject({ response: { status: 500 } });

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
  });

  it('does not swallow a successful response', async () => {
    mock.onGet('/some/resource').reply(200, { ok: true });

    const res = await api.get('/some/resource');

    expect(res.data).toEqual({ ok: true });
  });

  it('regression: an unauthenticated GET /auth/me does not loop : invalidateQueries on the ' +
    'still-mounted currentUser query would trigger an automatic refetch, 401 again, and repeat ' +
    'forever; setQueryData(null) must not provoke a refetch', async () => {
    useAuthStore.getState().reset();
    queryClient.clear();

    let getMeCalls = 0;
    mock.onGet('/auth/me').reply(() => {
      getMeCalls += 1;
      return [401, { detail: 'Not authenticated' }];
    });
    mock.onPost('/auth/refresh/').reply(401, { detail: 'No refresh token' });

    renderHook(() => useCurrentUserQuery(), {
      wrapper: ({ children }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
    });

    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(false));

    // Give any runaway invalidate-refetch loop a chance to fire before asserting.
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Exactly one GET /auth/me (plus its one refresh-and-retry attempt) :
    // never more, regardless of how long we wait.
    expect(getMeCalls).toBe(1);
  });
});
