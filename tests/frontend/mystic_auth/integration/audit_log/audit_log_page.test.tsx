import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import AuditLogPage from '@/audit_log/AuditLogPage';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test User',
    email: 'user@example.com',
    role: 'user',
    permissions,
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
  });
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={defaultSystem}>
        <MemoryRouter>
          <AuditLogPage />
        </MemoryRouter>
      </ChakraProvider>
    </QueryClientProvider>
  );
}

describe('AuditLogPage', () => {
  beforeEach(() => {
    mock.reset();
    mock.onGet('/authorization/audit-log/me').reply(200, []);
    mock.onGet('/audit/security-log/me').reply(200, []);
  });

  it('shows only "My activity" tabs for a caller with no admin audit permissions, in both categories', async () => {
    seed([]);
    renderPage();

    // Authorization decisions is the default category tab.
    expect(await screen.findByRole('tab', { name: 'My activity' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'All users' })).toBeNull();

    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    expect(await screen.findByRole('tab', { name: 'My activity' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'All users' })).toBeNull();
  });

  it('shows the "All users" tab for authorization decisions when the caller holds policies:read', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply(200, []);

    renderPage();

    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.getByRole('tab', { name: 'All users' })).toBeInTheDocument();

    // Security events is a separate category tab and shouldn't inherit
    // authorization's policies:read-gated "All users" tab.
    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.queryByRole('tab', { name: 'All users' })).toBeNull();
  });

  it('shows the "All users" tab in both categories when the caller holds policies:read and security_audit:read', async () => {
    seed(['policies:read', 'security_audit:read']);
    mock.onGet('/authorization/audit-log').reply(200, []);
    mock.onGet('/audit/security-log').reply(200, []);

    renderPage();

    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.getByRole('tab', { name: 'All users' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.getByRole('tab', { name: 'All users' })).toBeInTheDocument();
  });

  it('shows numbered pages from X-Total-Count and fetches the next page on click', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply((config) => {
      const offset = Number(config.params?.offset ?? 0);
      if (offset === 0) {
        return [200, [{ id: 1, user_email: 'a@example.com', action: 'users:read_own', resource_type: 'users', resource_identifier: null, allowed: true, candidate_policy_names: [], granting_policy_names: [], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' }], { 'x-total-count': '30' }];
      }
      return [200, [{ id: 2, user_email: 'b@example.com', action: 'users:read_own', resource_type: 'users', resource_identifier: null, allowed: true, candidate_policy_names: [], granting_policy_names: [], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' }], { 'x-total-count': '30' }];
    });

    renderPage();
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));

    expect(await screen.findByText('a@example.com')).toBeInTheDocument();
    // 30 rows / 25 per page = 2 pages.
    const page2Buttons = screen.getAllByRole('button', { name: 'Page 2' });
    expect(page2Buttons.length).toBeGreaterThan(0);

    await userEvent.click(page2Buttons[0]);
    expect(await screen.findByText('b@example.com')).toBeInTheDocument();
  });
});
