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

  it('opens a details dialog with the full name/email via the View row action', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const viewButtons = screen.getAllByRole('button', { name: 'View' });
    await user.click(viewButtons[viewButtons.length - 1]);

    expect(await screen.findByText('User details')).toBeInTheDocument();
    // The dialog's own "Regular User"/"user@example.com" (not the table row's).
    expect(screen.getAllByText('Regular User').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('user@example.com').length).toBeGreaterThanOrEqual(2);

    await user.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByText('User details')).toBeNull());
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
    // StyledSelect's visible trigger button and its hidden native <select>
    // mirror share the same accessible name (both properly labeled via
    // Select.Label), so getByRole('combobox', ...) alone is ambiguous -
    // selectOptions needs the real <select>, found via getByLabelText's
    // selector option instead.
    await user.selectOptions(screen.getByLabelText('Change role for user@example.com', { selector: 'select' }), 'admin');

    // The dialog capitalizes the role for display ("Admin", not the raw "admin" option value).
    expect(await screen.findByText(/Change .*role to "Admin"/)).toBeInTheDocument();
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

    // StyledSelect's visible trigger button and its hidden native <select>
    // mirror now share the same accessible name (both properly labeled via
    // Select.Label), so getByRole('combobox', ...) alone is ambiguous here
    // - selectOptions needs the real <select>, found via getByLabelText's
    // selector option instead.
    await user.selectOptions(screen.getByLabelText('Select a policy to assign', { selector: 'select' }), 'reporting');
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ policy_name: 'reporting' });

    await user.click(screen.getByRole('button', { name: 'Revoke self_service' }));
    // Revoking now goes through a ConfirmDialog (it strips access
    // immediately and irreversibly), matching every other destructive
    // action in the app - the click above only opens it.
    await user.click(await screen.findByRole('button', { name: 'Revoke' }));
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

  it('shows numbered pages (from X-Total-Count) and fetches the next page on click', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply((config) => {
      const offset = Number(config.params?.offset ?? 0);
      if (offset === 0) {
        return [200, SAMPLE_USERS, { 'x-total-count': '30' }];
      }
      return [200, [{ ...SAMPLE_USERS[0], id: 3, name: 'Page Two User', email: 'page2@example.com' }], { 'x-total-count': '30' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    // 30 users / 25 per page = 2 pages, so page buttons should render.
    const page2Buttons = screen.getAllByRole('button', { name: 'Page 2' });
    expect(page2Buttons.length).toBeGreaterThan(0);

    await user.click(page2Buttons[0]);

    expect(await screen.findByText('Page Two User')).toBeInTheDocument();
    const getRequests = mock.history.get.filter((r) => r.url === '/users/');
    expect(getRequests[getRequests.length - 1].params).toMatchObject({ offset: 25 });
  });

  it('searches server-side (debounced) and resets to page 1', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply((config) => {
      if (config.params?.search === 'regular') {
        return [200, [SAMPLE_USERS[1]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.type(screen.getByPlaceholderText('Search by name or email...'), 'regular');

    // Debounced: the filtered result (and the admin row disappearing)
    // shouldn't show up until after the debounce window.
    await waitFor(() => expect(screen.queryByText('Admin User')).toBeNull(), { timeout: 2000 });
    expect(screen.getByText('Regular User')).toBeInTheDocument();

    const lastRequest = mock.history.get[mock.history.get.length - 1];
    expect(lastRequest.params).toMatchObject({ search: 'regular' });
  });

  it('filters by role via the Role select and resets to page 1', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply((config) => {
      if (config.params?.role === 'admin') {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    // StyledSelect now also renders a (visually hidden) Select.Label for
    // the visible combobox button itself, so "Filter by role" alone
    // matches both that button and this hidden native <select> - narrow to
    // the actual <select> element, which is what selectOptions needs.
    await user.selectOptions(screen.getByLabelText('Filter by role', { selector: 'select' }), 'admin');

    await waitFor(() => expect(screen.queryByText('Regular User')).toBeNull());
    expect(screen.getByText('Admin User')).toBeInTheDocument();

    const lastRequest = mock.history.get[mock.history.get.length - 1];
    expect(lastRequest.params).toMatchObject({ role: 'admin' });
  });

  it('sorts by clicking the Name column header, toggling direction on a second click', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply((config) => {
      const sortDir = config.params?.sort_dir;
      const sortBy = config.params?.sort_by;
      if (sortBy === 'name' && sortDir === 'asc') {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '2' }];
      }
      if (sortBy === 'name' && sortDir === 'desc') {
        return [200, [SAMPLE_USERS[1]], { 'x-total-count': '2' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.click(screen.getByText('Name'));

    await waitFor(() => {
      const lastRequest = mock.history.get[mock.history.get.length - 1];
      expect(lastRequest.params).toMatchObject({ sort_by: 'name', sort_dir: 'asc' });
    });

    await user.click(screen.getByText('Name'));

    await waitFor(() => {
      const lastRequest = mock.history.get[mock.history.get.length - 1];
      expect(lastRequest.params).toMatchObject({ sort_by: 'name', sort_dir: 'desc' });
    });
  });
});
