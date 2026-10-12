import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import UsersPage from '@/users/UsersPage';
import { Toaster } from '@/ui/toaster/toaster';
import { toaster } from '@/ui/toaster/toasterInstance';

// BulkUserAccessDialog: fans one chosen direct permission out across
// every selected user via the real bulk endpoint, not a client-side loop over the single-item one.

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

function renderPage({ withToaster = false } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <UsersPage />
          {withToaster && <Toaster />}
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

async function selectAllRows(user: ReturnType<typeof userEvent.setup>) {
  const rowCheckboxes = await screen.findAllByRole('checkbox', { name: 'Select row' });
  for (const checkbox of rowCheckboxes) {
    await user.click(checkbox);
  }
}

describe('UsersPage bulk permission actions', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    // toaster is a module-level singleton; clear it so a leftover toast can't leak into the next test.
    await act(async () => {
      toaster.dismiss();
    });
  });

  it('bulk-grants a direct permission to every selected user via the real bulk endpoint', async () => {
    seed(['users:list_all', 'users:update_any', 'permissions:grant']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/permissions/catalog').reply(200, [
      { action: 'users:list_all', resource_type: 'users', description: "List and view any user's profile." },
    ]);
    mock.onPost('/authorization/bulk/permissions/assign').reply(200, {
      results: [
        { user_email: 'admin@example.com', identifier: 'users:list_all', status: 'success', error: null },
        { user_email: 'user@example.com', identifier: 'users:list_all', status: 'error', error: 'USER_NOT_FOUND' },
      ],
      success_count: 1,
      error_count: 1,
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Grant / revoke permission' }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByText("List and view any user's profile."));
    await user.click(within(dialog).getByRole('button', { name: 'Grant to selected' }));

    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      items: [
        { user_email: 'admin@example.com', action: 'users:list_all', resource_type: 'users', conditions: undefined },
        { user_email: 'user@example.com', action: 'users:list_all', resource_type: 'users', conditions: undefined },
      ],
    });
    expect(await screen.findByText('1 succeeded, 1 failed')).toBeInTheDocument();
  });

  it('does not still show the previous run\'s result summary when the bulk permission dialog is reopened', async () => {
    // Same regression as the bulk policy dialog's identical test: mutation
    // data must reset when the dialog is reopened.
    seed(['users:list_all', 'users:update_any', 'permissions:grant']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/permissions/catalog').reply(200, [
      { action: 'users:list_all', resource_type: 'users', description: "List and view any user's profile." },
    ]);
    mock.onPost('/authorization/bulk/permissions/assign').reply(200, {
      results: [{ user_email: 'admin@example.com', identifier: 'users:list_all', status: 'success', error: null }],
      success_count: 1,
      error_count: 0,
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Grant / revoke permission' }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByText("List and view any user's profile."));
    await user.click(within(dialog).getByRole('button', { name: 'Grant to selected' }));
    expect(await screen.findByText('1 succeeded, 0 failed')).toBeInTheDocument();

    const resultDialog = screen.getAllByRole('dialog').find((candidate) =>
      within(candidate).queryByText('Grant permission: users:list_all'),
    );
    expect(resultDialog).toBeDefined();
    expect(within(resultDialog!).getByText('users:list_all')).toBeInTheDocument();
    await user.click(within(resultDialog!).getByRole('button', { name: 'Close' }));
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    await user.click(await screen.findByRole('button', { name: 'Grant / revoke permission' }));
    const reopenedDialog = await screen.findByRole('dialog');
    expect(within(reopenedDialog).queryByText('1 succeeded, 0 failed')).toBeNull();
  });

  it('excludes an action the sole selected user (themselves) already effectively holds via a policy', async () => {
    // Regression: bulk-granting to a single selected row used to skip exclusion
    // filtering, letting an admin grant themselves an action already covered
    // by an assigned policy. Exclusion only applies when exactly one user is selected.
    seed(['users:list_all', 'users:update_any', 'permissions:grant']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/permissions/catalog').reply(200, [
      { action: 'users:list_all', resource_type: 'users', description: "List and view any user's profile." },
      { action: 'users:update_any', resource_type: 'users', description: "Update any user's profile." },
    ]);
    mock.onGet('/authorization/users/me/policies').reply(200, {
      user_email: 'admin@example.com',
      policies: [
        { id: 1, name: 'user_management', description: '', actions: ['users:list_all'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
      ],
    });
    mock.onGet('/authorization/users/me/permissions').reply(200, { user_email: 'admin@example.com', permissions: [] });

    const user = userEvent.setup();
    renderPage();

    await screen.findByText('Regular User');
    // Select only the admin's own row, the single-selection case this test exercises.
    const rowCheckboxes = await screen.findAllByRole('checkbox', { name: 'Select row' });
    await user.click(rowCheckboxes[0]);
    await user.click(await screen.findByRole('button', { name: 'Grant / revoke permission' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText("Update any user's profile.")).toBeInTheDocument();
    expect(within(dialog).queryByText("List and view any user's profile.")).toBeNull();
  });

  it('hides "Revoke from selected" in the bulk permission dialog when the caller lacks permissions:revoke', async () => {
    // Same regression as the policy dialog's identical test, for this
    // dialog's own "Revoke from selected" action.
    seed(['users:list_all', 'permissions:grant']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/permissions/catalog').reply(200, [
      { action: 'users:list_all', resource_type: 'users', description: "List and view any user's profile." },
    ]);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Grant / revoke permission' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('button', { name: 'Grant to selected' })).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: 'Revoke from selected' })).toBeNull();
  });
});
