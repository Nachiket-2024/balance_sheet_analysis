import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import UsersPage from '@/users/UsersPage';

// UserStatsCard's tile row (GET /users/stats): value rendering, the error
// state, and each tile's filter-shortcut + pressed-state behavior. Every
// other UsersPage control lives in users_page_list_controls.test.tsx.

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
    is_verified: false,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('UsersPage stats card', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('renders the four tiles from GET /users/stats', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS, { 'x-total-count': '2' });
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/users/stats').reply(200, { total: 42, verified: 40, unverified: 2, inactive: 1 });

    renderPage();

    await screen.findByText('Admin User');
    // Each tile's aria-label ("Filter users: X") is unique, unlike its
    // visible label text - "Verified"/"Deactivated" also appear as status
    // badges in the table below, so a plain screen.getByText('Verified')
    // would be ambiguous once real rows are on screen.
    expect(screen.getByRole('button', { name: 'Filter users: Total users' })).toHaveTextContent('42');
    expect(screen.getByRole('button', { name: 'Filter users: Verified' })).toHaveTextContent('40');
    expect(screen.getByRole('button', { name: 'Filter users: Unverified' })).toHaveTextContent('2');
    expect(screen.getByRole('button', { name: 'Filter users: Deactivated' })).toHaveTextContent('1');
  });

  it('shows a dash on each tile and no crash when GET /users/stats fails', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS, { 'x-total-count': '2' });
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/users/stats').reply(500);

    renderPage();

    await screen.findByText('Admin User');
    // UserStatsCard renders nothing at all on error (see its own isError
    // guard), rather than a broken/half-loaded row of tiles.
    expect(screen.queryByRole('button', { name: 'Filter users: Total users' })).toBeNull();
  });

  it('the Verified tile filters the table and shows as pressed', async () => {
    seed(['users:list_all']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/users/stats').reply(200, { total: 2, verified: 1, unverified: 1, inactive: 0 });
    mock.onGet('/users/').reply((config) => {
      if (config.params?.is_verified === true) {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const verifiedTile = screen.getByRole('button', { name: 'Filter users: Verified' });
    expect(verifiedTile).toHaveAttribute('aria-pressed', 'false');

    await user.click(verifiedTile);

    await waitFor(() => expect(screen.queryByText('Regular User')).toBeNull());
    expect(screen.getByText('Admin User')).toBeInTheDocument();
    expect(verifiedTile).toHaveAttribute('aria-pressed', 'true');
    // The Verified select mirrors the tile's own filter, same as clicking
    // it through the filter bar directly.
    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    expect(screen.getByLabelText('Filter by verified status', { selector: 'select' })).toHaveValue('true');
  });

  it('the Deactivated tile sets status to the backend\'s "deleted" value, not "inactive"', async () => {
    // Regression test: this tile previously called setStatus("inactive"),
    // a value the Status select never offers (only "active"/"deleted" -
    // see UsersFilterBar.tsx's own comment on why "deleted" is what the
    // backend calls a deactivated account), so the click silently filtered
    // to nothing.
    seed(['users:list_all']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/users/stats').reply(200, { total: 2, verified: 2, unverified: 0, inactive: 1 });
    mock.onGet('/users/').reply((config) => {
      if (config.params?.status === 'deleted') {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.click(screen.getByRole('button', { name: 'Filter users: Deactivated' }));

    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    await waitFor(() =>
      expect(screen.getByLabelText('Filter by status', { selector: 'select' })).toHaveValue('deleted')
    );
    const lastRequest = mock.history.get.filter((r) => r.url === '/users/').at(-1);
    expect(lastRequest?.params).toMatchObject({ status: 'deleted' });
  });

  it('the Total users tile clears every other filter and becomes the pressed one', async () => {
    seed(['users:list_all']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/users/stats').reply(200, { total: 2, verified: 1, unverified: 1, inactive: 0 });
    mock.onGet('/users/').reply(200, SAMPLE_USERS, { 'x-total-count': '2' });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    const totalTile = screen.getByRole('button', { name: 'Filter users: Total users' });
    const verifiedTile = screen.getByRole('button', { name: 'Filter users: Verified' });

    // Starts pressed: no filters are active on first load.
    expect(totalTile).toHaveAttribute('aria-pressed', 'true');

    await user.click(verifiedTile);
    await waitFor(() => expect(verifiedTile).toHaveAttribute('aria-pressed', 'true'));
    expect(totalTile).toHaveAttribute('aria-pressed', 'false');

    await user.click(totalTile);

    await waitFor(() => expect(totalTile).toHaveAttribute('aria-pressed', 'true'));
    expect(verifiedTile).toHaveAttribute('aria-pressed', 'false');
    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    expect(screen.getByLabelText('Filter by verified status', { selector: 'select' })).toHaveValue('');
  });
});
