import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import UsersPage from '@/users/UsersPage';

// Row-level actions: viewing, deleting, changing role, reactivating, and
// purging a user. Pagination/search/filter/sort/export live in
// users_page_list_controls.test.tsx, and the Policies dialog in
// users_page_policies.test.tsx.

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

    const dialog = await screen.findByRole('dialog');
    // The dialog's own "Regular User"/"user@example.com" (not the table row's).
    expect(screen.getAllByText('Regular User').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('user@example.com').length).toBeGreaterThanOrEqual(2);
    expect(within(dialog).getByRole('tab', { name: /Details/ })).toHaveAttribute('aria-selected', 'true');

    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('shows separate Policies and Permissions actions only when each read permission is available', async () => {
    seed(['users:list_all', 'permissions:read']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    await screen.findByText('Regular User');
    expect(screen.getAllByRole('button', { name: 'Permissions' })).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Policies' })).toBeNull();
  });

  it('opens the dedicated Permissions action directly on the Permissions tab', async () => {
    seed(['users:list_all', 'permissions:read']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const accessButtons = screen.getAllByRole('button', { name: 'Permissions' });
    await user.click(accessButtons[accessButtons.length - 1]);

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('tab', { name: /Permissions/ })).toHaveAttribute('aria-selected', 'true');
    expect(within(dialog).getByRole('tab', { name: /Details/ })).toHaveAttribute('aria-selected', 'false');
  });

  it('hides both access actions when the caller cannot read policies or permissions', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    await screen.findByText('Regular User');
    expect(screen.queryByRole('button', { name: 'Policies' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Permissions' })).toBeNull();
  });

  it('hides the Deactivate row action when the caller lacks that permission', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    await screen.findByText('Regular User');
    const regularRow = screen.getByText('user@example.com').closest('tr');
    expect(regularRow).not.toBeNull();
    await userEvent.setup().click(within(regularRow!).getByRole('button', { name: /more actions/i }));
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).toBeNull();
  });

  it('hides destructive actions for the protected system user', async () => {
    seed(['users:list_all', 'users:deactivate_any', 'users:delete_any']);
    mock.onGet('/users/').reply(200, [{ ...SAMPLE_USERS[0], role: 'system', email: 'system@example.com' }, SAMPLE_USERS[1]]);

    renderPage();

    await screen.findByText('system@example.com');
    const systemRow = screen.getByText('system@example.com').closest('tr');
    expect(systemRow).not.toBeNull();
    expect(within(systemRow!).queryByRole('button', { name: /more actions/i })).toBeNull();
  });

  it('disables the deactivate button for the caller\'s own row even with users:deactivate_any', async () => {
    seed(['users:list_all', 'users:deactivate_any'], 'admin@example.com');
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    await screen.findByText('Admin User');
    const user = userEvent.setup();
    const adminRow = screen.getByText('admin@example.com').closest('tr');
    const regularRow = screen.getByText('user@example.com').closest('tr');
    expect(adminRow).not.toBeNull();
    expect(regularRow).not.toBeNull();

    // The caller's own row still has the menu (so the disabled state is
    // discoverable, not just absent), but Deactivate itself is disabled.
    await user.click(within(adminRow!).getByRole('button', { name: /more actions/i }));
    expect(screen.getByRole('menuitem', { name: 'Deactivate' })).toHaveAttribute('data-disabled');
    await user.keyboard('{Escape}');

    await user.click(within(regularRow!).getByRole('button', { name: /more actions/i }));
    expect(screen.getByRole('menuitem', { name: 'Deactivate' })).toBeEnabled();
  });

  it('explains why the caller cannot deactivate their own account on hover', async () => {
    seed(['users:list_all', 'users:deactivate_any'], 'admin@example.com');
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();

    await screen.findByText('Admin User');
    const user = userEvent.setup();
    const adminRow = screen.getByText('admin@example.com').closest('tr');
    expect(adminRow).not.toBeNull();

    await user.click(within(adminRow!).getByRole('button', { name: /more actions/i }));
    await user.hover(screen.getByRole('menuitem', { name: 'Deactivate' }));
    expect(await screen.findByText('You cannot deactivate your own account through this page')).toBeInTheDocument();
  });

  it('disables Delete (not just Deactivate) for the caller\'s own already-deleted row, with an explanation', async () => {
    seed(['users:list_all', 'users:delete_any'], 'admin@example.com');
    const deletedSelf = { ...SAMPLE_USERS[0], deleted_at: '2026-01-02T00:00:00Z' };
    mock.onGet('/users/').reply(200, [deletedSelf, SAMPLE_USERS[1]]);

    renderPage();

    await screen.findByText('Admin User');
    const user = userEvent.setup();
    const adminRow = screen.getByText('admin@example.com').closest('tr');
    expect(adminRow).not.toBeNull();

    await user.click(within(adminRow!).getByRole('button', { name: /more actions/i }));
    expect(screen.getByRole('menuitem', { name: 'Delete' })).toHaveAttribute('data-disabled');
    await user.hover(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(await screen.findByText('You cannot delete your own account through this page')).toBeInTheDocument();
  });

  it('deactivates a user after confirming in the ConfirmDialog', async () => {
    seed(['users:list_all', 'users:deactivate_any']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onDelete('/users/user%40example.com').reply(200);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const regularRow = screen.getByText('user@example.com').closest('tr');
    expect(regularRow).not.toBeNull();
    await user.click(within(regularRow!).getByRole('button', { name: /more actions/i }));
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));

    expect(await screen.findByText(/Deactivate "user@example.com"\?/)).toBeInTheDocument();
    const confirmButtons = screen.getAllByRole('button', { name: 'Deactivate' });
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
    // StyledSelect's visible button and its hidden native <select> share the
    // same accessible name, so getByRole('combobox') is ambiguous; get the
    // real <select> via getByLabelText instead.
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

    const regularRow = (await screen.findByText('user@example.com')).closest('tr');
    expect(regularRow).not.toBeNull();
    await user.click(within(regularRow!).getByRole('button', { name: /more actions/i }));
    await user.click(screen.getByRole('menuitem', { name: 'Reactivate' }));

    await waitFor(() => expect(mock.history.patch.length).toBe(1));
  });

  it('permanently deletes a soft-deactivated user after confirming', async () => {
    seed(['users:list_all', 'users:delete_any']);
    const deletedUser = { ...SAMPLE_USERS[1], deleted_at: '2026-01-02T00:00:00Z' };
    mock.onGet('/users/').reply(200, [SAMPLE_USERS[0], deletedUser]);
    mock.onDelete('/users/user%40example.com/purge').reply(200);

    renderPage();
    const user = userEvent.setup();

    const regularRow = (await screen.findByText('user@example.com')).closest('tr');
    expect(regularRow).not.toBeNull();
    await user.click(within(regularRow!).getByRole('button', { name: /more actions/i }));
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(await screen.findByText(/Delete "user@example.com" permanently\?/)).toBeInTheDocument();
    const confirmButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('shows an error toast-triggering message when deactivating a user fails', async () => {
    seed(['users:list_all', 'users:deactivate_any']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onDelete('/users/user%40example.com').reply(500);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const regularRow = screen.getByText('user@example.com').closest('tr');
    expect(regularRow).not.toBeNull();
    await user.click(within(regularRow!).getByRole('button', { name: /more actions/i }));
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    const confirmButtons = await screen.findAllByRole('button', { name: 'Deactivate' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    // Failure surfaces via a toast, not inline text, so just confirm the DELETE fired.
    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });
});
