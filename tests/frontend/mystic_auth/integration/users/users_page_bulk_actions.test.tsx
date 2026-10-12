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

// Multi-select (DataTable's selectable/selectedKeys/onSelectionChange, wired
// up in UsersPage.tsx) and the bulk role-set dialog. Bulk policy/permission
// coverage lives in the dedicated users_page_bulk_policy_actions.test.tsx /
// users_page_bulk_permission_actions.test.tsx once this file passed the
// repo's file-length guideline; this file keeps only what's unique to
// multi-select itself and to the bulk role dialog.

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

describe('UsersPage bulk actions', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    // toaster is a module-level singleton that outlives each test's render
    // tree; clear it so a leftover toast from one test can't leak into the next.
    await act(async () => {
      toaster.dismiss();
    });
  });

  it('always renders the bulk action buttons, enabling them only once rows are selected', async () => {
    seed(['users:list_all', 'policies:assign']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    // Present but disabled with nothing selected - not hidden.
    expect(await screen.findByRole('button', { name: 'Assign / revoke policy' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Clear selection' })).toBeDisabled();

    const rowCheckboxes = await screen.findAllByRole('checkbox', { name: 'Select row' });
    await user.click(rowCheckboxes[0]);
    // The "1 selected" text is DataTable's own summary (see DataTable.tsx);
    // this only checks the bulk-action buttons enable/disable correctly.
    expect(await screen.findByRole('button', { name: 'Assign / revoke policy' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Clear selection' })).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Clear selection' }));
    expect(await screen.findByRole('button', { name: 'Assign / revoke policy' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Clear selection' })).toBeDisabled();
  });

  it('bulk-sets the role for every selected user via the real bulk endpoint', async () => {
    seed(['users:list_all', 'users:assign_role']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    mock.onPost('/authorization/bulk/users/role').reply(200, {
      results: [
        { user_email: 'admin@example.com', identifier: 'admin', status: 'success', error: null },
        { user_email: 'user@example.com', identifier: 'admin', status: 'success', error: null },
      ],
      success_count: 2,
      error_count: 0,
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await selectAllRows(user);
    await user.click(await screen.findByRole('button', { name: 'Set role' }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: 'Admin' }));
    await user.click(within(dialog).getByRole('button', { name: 'Set role for selected' }));

    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      items: [
        { user_email: 'admin@example.com', role: 'admin' },
        { user_email: 'user@example.com', role: 'admin' },
      ],
    });
    expect(await screen.findByText('2 succeeded, 0 failed')).toBeInTheDocument();
    const resultDialog = screen.getAllByRole('dialog').find((candidate) =>
      within(candidate).queryByText('Set role: admin'),
    );
    expect(resultDialog).toBeDefined();
    expect(within(resultDialog!).getAllByText('admin')).toHaveLength(2);
  });

  it('only selects rows by clicking their content once "Select mode" is turned on', async () => {
    seed(['users:list_all', 'policies:assign']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');

    // Off by default: clicking a row's plain text must not select it (it
    // would otherwise fight double-click/drag-select-to-copy on cell text).
    await user.click(screen.getByText('Regular User'));
    expect(screen.getByRole('button', { name: 'Assign / revoke policy' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Select mode' }));
    await user.click(screen.getByText('Regular User'));
    expect(await screen.findByRole('button', { name: 'Assign / revoke policy' })).toBeEnabled();
  });
});
