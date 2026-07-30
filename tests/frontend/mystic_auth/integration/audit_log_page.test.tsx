import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
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

  it('shows only "My activity" tabs for a caller with no admin audit permissions', async () => {
    seed([]);
    renderPage();

    // Two "My activity" triggers (one per log type) and no "All users" triggers
    expect(await screen.findAllByRole('tab', { name: 'My activity' })).toHaveLength(2);
    expect(screen.queryByRole('tab', { name: 'All users' })).toBeNull();
  });

  it('shows the "All users" tab for authorization decisions when the caller holds policies:read', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply(200, []);

    renderPage();

    await screen.findAllByRole('tab', { name: 'My activity' });
    expect(screen.getAllByRole('tab', { name: 'All users' })).toHaveLength(1);
  });

  it('shows both "All users" tabs when the caller holds policies:read and security_audit:read', async () => {
    seed(['policies:read', 'security_audit:read']);
    mock.onGet('/authorization/audit-log').reply(200, []);
    mock.onGet('/audit/security-log').reply(200, []);

    renderPage();

    await screen.findAllByRole('tab', { name: 'My activity' });
    expect(screen.getAllByRole('tab', { name: 'All users' })).toHaveLength(2);
  });
});
