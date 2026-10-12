import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import UsersPage from '@/users/UsersPage';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seed() {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test Admin',
    email: 'admin@example.com',
    role: 'admin',
    permissions: ['users:list_all', 'policies:read', 'policies:assign', 'policies:revoke', 'permissions:read', 'permissions:revoke', 'support:read'],
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
    brand_color: null,
  });
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('UsersPage access dialog self protection', () => {
  beforeEach(() => {
    mock.reset();
    seed();
    mock.onGet('/users/').reply(200, [
      { id: 1, name: 'Admin User', email: 'admin@example.com', role: 'admin', is_verified: true, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      { id: 2, name: 'Regular User', email: 'user@example.com', role: 'user', is_verified: true, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
    ]);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'self_service', description: '', actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
      { id: 2, name: 'support-agent', description: '', actions: ['support:read'], resource_type: 'support', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onGet('/authorization/users/me/policies').reply(200, {
      user_email: 'admin@example.com',
      policies: [{ id: 1, name: 'self_service', description: '', actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null }],
    });
    mock.onGet('/authorization/users/me/permissions').reply(200, { user_email: 'admin@example.com', permissions: [] });
  });

  it("locks a baseline policy's toggle but not an ordinary one when viewing the caller's own access", async () => {
    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Admin User');
    const accessButtons = screen.getAllByRole('button', { name: 'Policies' });
    await user.click(accessButtons[0]);
    await user.click(within(await screen.findByRole('dialog')).getByRole('tab', { name: /Policies/ }));

    const dialog = await screen.findByRole('dialog');
    await within(dialog).findByText('self_service');
    expect(screen.queryByText(/This is your own account/)).not.toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /Revoke self_service|self_service/ })).toBeDisabled();
    expect(screen.getByRole('switch', { name: 'support-agent' })).toBeEnabled();
  });
});
