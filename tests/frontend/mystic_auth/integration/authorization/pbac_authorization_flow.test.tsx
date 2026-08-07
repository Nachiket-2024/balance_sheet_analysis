import type { ReactNode } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import { useLoginMutation } from '@/auth/login/useLoginMutation';
import { useAuthSession } from '@/auth/current_user/useCurrentUserQuery';
import { Authorized } from '@/authorization/Authorized';
import { IfCan } from '@/authorization/IfCan';

const mock = new MockAdapter(api);
const PASSWORD = 'StrongPass123!';
const initialAuthState = useAuthStore.getState();

function queryWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

function Dashboard() {
  return (
    <div>
      <Authorized permission="users:list_all" fallback={<div>No admin access</div>}>
        <div>Admin Panel</div>
      </Authorized>
      <IfCan action="documents:view">
        <div>Document Viewer</div>
      </IfCan>
    </div>
  );
}

function renderDashboard() {
  return render(
    <ChakraProvider value={defaultSystem}>
      <Dashboard />
    </ChakraProvider>
  );
}

describe('PBAC end-to-end: login -> permissions loaded -> conditional UI renders correctly', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('shows only the UI gated behind permissions the logged-in user actually holds', async () => {
    mock.onPost('/auth/login').reply(200, { message: 'Login successful' });
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      permissions: ['documents:view'], // holds this, NOT users:list_all
    });

    renderDashboard();

    // Before login resolves, auth status is unknown, so neither gated
    // element nor its fallback should render yet.
    expect(screen.queryByText('Admin Panel')).toBeNull();
    expect(screen.queryByText('No admin access')).toBeNull();
    expect(screen.queryByText('Document Viewer')).toBeNull();

    const { result } = renderHook(() => useLoginMutation(), { wrapper: queryWrapper() });
    await act(async () => {
      await result.current.mutateAsync({ email: 'user@example.com', password: PASSWORD });
    });

    await waitFor(() => {
      expect(screen.getByText('Document Viewer')).toBeInTheDocument();
    });
    expect(screen.getByText('No admin access')).toBeInTheDocument();
    expect(screen.queryByText('Admin Panel')).toBeNull();
  });

  it('grants access to admin-gated UI when the user holds that permission too', async () => {
    mock.onPost('/auth/login').reply(200, { message: 'Login successful' });
    mock.onGet('/auth/me').reply(200, {
      name: 'Admin User',
      email: 'admin@example.com',
      role: 'admin',
      permissions: ['documents:view', 'users:list_all'],
    });

    renderDashboard();

    const { result } = renderHook(() => useLoginMutation(), { wrapper: queryWrapper() });
    await act(async () => {
      await result.current.mutateAsync({ email: 'admin@example.com', password: PASSWORD });
    });

    await waitFor(() => {
      expect(screen.getByText('Admin Panel')).toBeInTheDocument();
    });
    expect(screen.getByText('Document Viewer')).toBeInTheDocument();
    expect(screen.queryByText('No admin access')).toBeNull();
  });

  it('a failed login never reveals protected content, regardless of what the session check later resolves to', async () => {
    // A failed login short-circuits before the profile fetch, so
    // isAuthenticated stays null until App.tsx's session-sync hook
    // independently resolves it : simulated here via useAuthSession.
    mock.onPost('/auth/login').reply(401, { detail: 'Invalid credentials' });
    mock.onGet('/auth/me').reply(401, { detail: 'Not authenticated' });

    renderDashboard();

    const { result: loginResult } = renderHook(() => useLoginMutation(), { wrapper: queryWrapper() });
    await act(async () => {
      await result_ignoreRejection(loginResult.current.mutateAsync({ email: 'user@example.com', password: 'wrong-password' }));
    });
    expect(screen.queryByText('Admin Panel')).toBeNull();
    expect(screen.queryByText('Document Viewer')).toBeNull();

    renderHook(() => useAuthSession(), { wrapper: queryWrapper() });

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
    // Now resolved to unauthenticated: fallback renders, protected content doesn't.
    expect(screen.getByText('No admin access')).toBeInTheDocument();
    expect(screen.queryByText('Admin Panel')).toBeNull();
    expect(screen.queryByText('Document Viewer')).toBeNull();
  });
});

// Swallow the expected rejection from a failed mutateAsync : the test only
// cares about the resulting auth-store/DOM state.
async function result_ignoreRejection(promise: Promise<unknown>): Promise<void> {
  await promise.catch(() => undefined);
}
