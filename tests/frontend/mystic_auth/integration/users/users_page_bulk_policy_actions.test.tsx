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

// BulkUserAccessDialog: fans one chosen policy out across every selected
// user via the real bulk endpoint, not a client-side loop over the single-item one.

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

describe('UsersPage bulk policy actions', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    // toaster is a module-level singleton; clear it so a leftover toast can't leak into the next test.
    await act(async () => {
      toaster.dismiss();
    });
  });

  it('bulk-assigns a policy to every selected user via the real bulk endpoint', async () => {
    seed(['users:list_all', 'policies:assign', 'policies:read', 'reports:view']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'reporting', description: '', actions: ['reports:view'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onPost('/authorization/bulk/policies/assign').reply(200, {
      results: [
        { user_email: 'admin@example.com', identifier: 'reporting', status: 'success', error: null },
        { user_email: 'user@example.com', identifier: 'reporting', status: 'success', error: null },
      ],
      success_count: 2,
      error_count: 0,
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Assign / revoke policy' }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: 'reporting' }));
    await user.click(within(dialog).getByRole('button', { name: 'Assign to selected' }));

    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      items: [
        { user_email: 'admin@example.com', policy_name: 'reporting' },
        { user_email: 'user@example.com', policy_name: 'reporting' },
      ],
    });
    expect(await screen.findByText('2 succeeded, 0 failed')).toBeInTheDocument();
  });

  it('does not still show the previous run\'s result summary when the bulk policy dialog is reopened', async () => {
    // Regression: react-query mutations keep their last `.data` around across
    // remounts, so a reopened dialog used to show the previous run's summary.
    seed(['users:list_all', 'policies:assign', 'policies:read', 'reports:view']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'reporting', description: '', actions: ['reports:view'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onPost('/authorization/bulk/policies/assign').reply(200, {
      results: [{ user_email: 'admin@example.com', identifier: 'reporting', status: 'success', error: null }],
      success_count: 1,
      error_count: 0,
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Assign / revoke policy' }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: 'reporting' }));
    await user.click(within(dialog).getByRole('button', { name: 'Assign to selected' }));
    expect(await screen.findByText('1 succeeded, 0 failed')).toBeInTheDocument();

    const resultDialog = screen.getAllByRole('dialog').find((candidate) =>
      within(candidate).queryByText('Assign policy: reporting'),
    );
    expect(resultDialog).toBeDefined();
    expect(within(resultDialog!).getByText('reporting')).toBeInTheDocument();
    await user.click(within(resultDialog!).getByRole('button', { name: 'Close' }));
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    await user.click(await screen.findByRole('button', { name: 'Assign / revoke policy' }));
    const reopenedDialog = await screen.findByRole('dialog');
    expect(within(reopenedDialog).queryByText('1 succeeded, 0 failed')).toBeNull();
  });

  it('surfaces a toast when the bulk-assign request itself fails (not a per-item error)', async () => {
    // Regression: a request-level failure used to leave the button's spinner
    // just stop, with no error feedback.
    seed(['users:list_all', 'policies:assign', 'policies:read', 'reports:view']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'reporting', description: '', actions: ['reports:view'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onPost('/authorization/bulk/policies/assign').reply(500, { detail: 'bulk assign failed' });

    renderPage({ withToaster: true });
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Assign / revoke policy' }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: 'reporting' }));
    await user.click(within(dialog).getByRole('button', { name: 'Assign to selected' }));

    expect(await screen.findByText('bulk assign failed')).toBeInTheDocument();
  });

  it('excludes a policy that adds nothing the sole selected user (themselves) does not already effectively hold, from the bulk-assign list', async () => {
    // Same regression as the matching test for direct permission grants.
    seed(['users:list_all', 'policies:assign', 'reports:view']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'user_management', description: '', actions: ['users:list_all'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
      { id: 2, name: 'reporting', description: '', actions: ['reports:view'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
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
    const rowCheckboxes = await screen.findAllByRole('checkbox', { name: 'Select row' });
    await user.click(rowCheckboxes[0]);
    await user.click(await screen.findByRole('button', { name: 'Assign / revoke policy' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('reporting')).toBeInTheDocument();
    expect(within(dialog).queryByText('user_management')).toBeNull();
  });

  it('shows "already had this" for a bulk-assign item the backend reports as a no-op', async () => {
    // status "already_held" is a genuine no-op the backend reports separately
    // from "success", since the picker doesn't filter per-user across a bulk selection.
    seed(['users:list_all', 'policies:assign', 'policies:read', 'reports:view']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'reporting', description: '', actions: ['reports:view'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onPost('/authorization/bulk/policies/assign').reply(200, {
      results: [
        { user_email: 'admin@example.com', identifier: 'reporting', status: 'success', error: null },
        { user_email: 'user@example.com', identifier: 'reporting', status: 'already_held', error: null },
      ],
      success_count: 2,
      error_count: 0,
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Assign / revoke policy' }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: 'reporting' }));
    await user.click(within(dialog).getByRole('button', { name: 'Assign to selected' }));

    expect(await screen.findByText('2 succeeded, 0 failed')).toBeInTheDocument();
    expect(screen.getByText('already had this')).toBeInTheDocument();
  });

  it('hides "Remove from selected" in the bulk policy dialog when the caller lacks policies:revoke', async () => {
    // The toolbar button is gated on policies:assign, but the dialog's own
    // "Remove from selected" action must independently gate on policies:revoke.
    seed(['users:list_all', 'policies:assign', 'policies:read']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'reporting', description: '', actions: ['reports:view'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Assign / revoke policy' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('button', { name: 'Assign to selected' })).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: 'Remove from selected' })).toBeNull();
  });
});
