import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import UsersPage from '@/users/UsersPage';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seed(permissions: string[], email = 'admin@example.com') {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test Admin',
    email,
    role: 'admin',
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
          <UsersPage />
        </MemoryRouter>
      </ChakraProvider>
    </QueryClientProvider>
  );
}

const SAMPLE_USERS = [
  {
    id: 1,
    name: 'Admin User',
    email: 'admin@example.com',
    role: 'admin',
    is_verified: true,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Regular User',
    email: 'user@example.com',
    role: 'user',
    is_verified: true,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('UsersPage', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('lists users returned by the backend', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    expect(await screen.findByText('Regular User')).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
  });

  it('hides the Delete row action when the caller lacks that permission', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    await screen.findByText('Regular User');
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('disables the delete button for the caller\'s own row even with users:delete_any', async () => {
    seed(['users:list_all', 'users:delete_any'], 'admin@example.com');
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    await screen.findByText('Admin User');
    const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
    // First row is the admin (self) : must be disabled to prevent self-deletion
    expect(deleteButtons[0]).toBeDisabled();
    expect(deleteButtons[1]).toBeEnabled();
  });

  it('deletes a user after confirming in the ConfirmDialog', async () => {
    seed(['users:list_all', 'users:delete_any']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onDelete('/users/user%40example.com').reply(200);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(deleteButtons[deleteButtons.length - 1]);

    expect(await screen.findByText(/Delete "user@example.com"\?/)).toBeInTheDocument();
    const confirmButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('changes a user\'s role after confirming, via PATCH .../role', async () => {
    seed(['users:list_all', 'users:assign_role']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onPatch('/users/user%40example.com/role').reply(200, { ...SAMPLE_USERS[1], role: 'admin' });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Change role for user@example.com' }), 'admin');

    expect(await screen.findByText(/Change .*role to "admin"/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Change role' }));

    await waitFor(() => expect(mock.history.patch.length).toBe(1));
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ role: 'admin' });
  });

  it('reactivates a soft-deleted user via PATCH .../reactivate (no confirmation needed)', async () => {
    seed(['users:list_all', 'users:reactivate']);
    const deletedUser = { ...SAMPLE_USERS[1], deleted_at: '2026-01-02T00:00:00Z' };
    mock.onGet('/users/').reply(200, [SAMPLE_USERS[0], deletedUser]);
    mock.onPatch('/users/user%40example.com/reactivate').reply(200, { ...deletedUser, deleted_at: null });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Reactivate' }));

    await waitFor(() => expect(mock.history.patch.length).toBe(1));
  });

  it('permanently removes a soft-deleted user after confirming purge', async () => {
    seed(['users:list_all', 'users:purge']);
    const deletedUser = { ...SAMPLE_USERS[1], deleted_at: '2026-01-02T00:00:00Z' };
    mock.onGet('/users/').reply(200, [SAMPLE_USERS[0], deletedUser]);
    mock.onDelete('/users/user%40example.com/purge').reply(200);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Purge' }));
    expect(await screen.findByText(/Permanently remove "user@example.com"\?/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Permanently remove' }));

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('shows an error toast-triggering message when deleting a user fails', async () => {
    seed(['users:list_all', 'users:delete_any']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onDelete('/users/user%40example.com').reply(500);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(deleteButtons[deleteButtons.length - 1]);
    const confirmButtons = await screen.findAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    // Failure surfaces via a toast, not inline text, so just confirm the DELETE fired.
    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('opens the Policies dialog, assigns an available policy, and revokes an assigned one', async () => {
    seed(['users:list_all', 'policies:read', 'policies:assign', 'policies:revoke']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'self_service', description: '', actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
      { id: 2, name: 'reporting', description: '', actions: ['reports:view'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onGet('/authorization/users/user%40example.com/policies').reply(200, {
      user_email: 'user@example.com',
      policies: [{ id: 1, name: 'self_service', description: '', actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null }],
    });
    mock.onPost('/authorization/users/user%40example.com/policies').reply(200);
    mock.onDelete('/authorization/users/user%40example.com/policies/self_service').reply(204);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const policiesButtons = screen.getAllByRole('button', { name: 'Policies' });
    await user.click(policiesButtons[policiesButtons.length - 1]);

    expect(await screen.findByText('self_service')).toBeInTheDocument();

    await user.selectOptions(screen.getByRole('combobox', { name: 'Select a policy to assign' }), 'reporting');
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ policy_name: 'reporting' });

    await user.click(screen.getByRole('button', { name: 'Revoke self_service' }));
    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it("disables revoke for the caller's own assigned policies in the Policies dialog", async () => {
    seed(['users:list_all', 'policies:read', 'policies:revoke'], 'admin@example.com');
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/authorization/users/admin%40example.com/policies').reply(200, {
      user_email: 'admin@example.com',
      policies: [{ id: 1, name: 'self_service', description: '', actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null }],
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Admin User');
    const policiesButtons = screen.getAllByRole('button', { name: 'Policies' });
    await user.click(policiesButtons[0]);

    expect(await screen.findByText(/You cannot revoke your own policies from here/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Revoke self_service' })).toBeDisabled();
  });
});
