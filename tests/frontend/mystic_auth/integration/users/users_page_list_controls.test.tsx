import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import UsersPage from '@/users/UsersPage';
import { formatPolicyActionLabel } from '@/policies/policyCardHelpers';

// Pagination, server-side search/filter/sort, and CSV export. Row actions
// live in users_page.test.tsx, and the Policies dialog in
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

function renderPage(initialEntries = ['/users']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>
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

describe('UsersPage list controls', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('keeps filter controls hidden until the Filters button is selected', async () => {
    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS, { 'x-total-count': '2' });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    expect(screen.queryByLabelText('Filter by role', { selector: 'select' })).toBeNull();

    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    expect(screen.getByLabelText('Filter by role', { selector: 'select' })).toBeInTheDocument();
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

  it('hydrates the policy filter from a URL deep link', async () => {
    seed(['users:list_all']);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'report_viewer', description: null, actions: ['reports:read'], resource_type: 'reports', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onGet('/users/').reply((config) => {
      if (config.params?.policy === 'report_viewer') {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage(['/users?policy=report_viewer']);

    expect(await screen.findByText('Admin User')).toBeInTheDocument();
    expect(screen.queryByText('Regular User')).toBeNull();
    expect(mock.history.get.filter((request) => request.url === '/users/').at(-1)?.params)
      .toMatchObject({ policy: 'report_viewer' });
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
    expect(await screen.findByText('Regular User')).toBeInTheDocument();

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
    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    // "Filter by role" alone matches both the visible button and its hidden
    // native <select>; narrow to the <select>, which selectOptions needs.
    await user.selectOptions(screen.getByLabelText('Filter by role', { selector: 'select' }), 'admin');

    await waitFor(() => expect(screen.queryByText('Regular User')).toBeNull());
    expect(screen.getByText('Admin User')).toBeInTheDocument();

    const lastRequest = mock.history.get[mock.history.get.length - 1];
    expect(lastRequest.params).toMatchObject({ role: 'admin' });
  });

  it('filters by policy via the Policy select and resets to page 1', async () => {
    seed(['users:list_all']);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'self_service', description: null, actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
      { id: 2, name: 'user_management', description: null, actions: ['users:list_all'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onGet('/users/').reply((config) => {
      if (config.params?.policy === 'user_management') {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    await user.click(screen.getByRole('button', { name: 'Filter by policy' }));
    await user.click(screen.getByRole('button', { name: 'user_management' }));

    await waitFor(() => expect(screen.queryByText('Regular User')).toBeNull());
    expect(screen.getByText('Admin User')).toBeInTheDocument();

    const lastRequest = mock.history.get.filter((r) => r.url === '/users/').at(-1);
    expect(lastRequest?.params).toMatchObject({ policy: 'user_management' });
  });

  it('keeps policy and verification filters conjunctive', async () => {
    seed(['users:list_all']);
    mock.onGet('/authorization/policies').reply(200, [
      { id: 1, name: 'self_service', description: null, actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: null },
    ]);
    mock.onGet('/users/').reply((config) => {
      if (config.params?.policy === 'self_service' && config.params?.is_verified === true) {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    await user.click(screen.getByRole('button', { name: 'Filter by policy' }));
    await user.click(screen.getByRole('button', { name: 'self_service' }));
    await user.selectOptions(screen.getByLabelText('Filter by verified status', { selector: 'select' }), 'true');

    await waitFor(() => expect(screen.queryByText('Regular User')).toBeNull());
    expect(screen.getByText('Admin User')).toBeInTheDocument();
    const lastRequest = mock.history.get.filter((r) => r.url === '/users/').at(-1);
    expect(lastRequest?.params).toMatchObject({ policy: 'self_service', is_verified: true });
  });

  it('filters by permission via the Permission picker and resets to page 1', async () => {
    seed(['users:list_all']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/users/').reply((config) => {
      if (config.params?.permission === 'users:list_all') {
        return [200, [SAMPLE_USERS[0]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_USERS, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.click(screen.getByRole('button', { name: /^Filters/ }));
    await user.click(screen.getByRole('button', { name: 'Filter by permission' }));
    await user.click(await screen.findByRole('button', { name: formatPolicyActionLabel('users:list_all') }));

    await waitFor(() => expect(screen.queryByText('Regular User')).toBeNull());
    expect(screen.getByText('Admin User')).toBeInTheDocument();

    const lastRequest = mock.history.get.filter((r) => r.url === '/users/').at(-1);
    expect(lastRequest?.params).toMatchObject({ permission: 'users:list_all' });
  });

  it('exports the current filters as CSV and triggers a browser download', async () => {
    // jsdom has no real createObjectURL/revokeObjectURL (see
    // useExportUsersMutation); fake them for this test only.
    const createObjectURL = vi.fn().mockReturnValue('blob:mock-url');
    const revokeObjectURL = vi.fn();
    // jsdom cannot perform a real document navigation when the download
    // anchor is clicked. Mock the browser primitive at the boundary; the
    // assertions below still cover the request, filename, and blob cleanup.
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });

    seed(['users:list_all']);
    mock.onGet('/users/').reply(200, SAMPLE_USERS);
    const csvBody = 'id,name,email,role,is_verified,is_active,status,created_at\n';
    mock.onGet('/users/export').reply(200, csvBody, {
      'content-disposition': 'attachment; filename="users_export_20260101T000000Z.csv"',
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('Regular User');
    await user.click(screen.getByRole('button', { name: 'Export CSV' }));

    await waitFor(() => expect(mock.history.get.some((r) => r.url === '/users/export')).toBe(true));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1));
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    expect(click).toHaveBeenCalled();

    click.mockRestore();
    vi.unstubAllGlobals();
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
    await user.click(screen.getByText('Name / Email'));

    await waitFor(() => {
      const lastRequest = mock.history.get[mock.history.get.length - 1];
      expect(lastRequest.params).toMatchObject({ sort_by: 'name', sort_dir: 'asc' });
    });

    await user.click(screen.getByText('Name / Email'));

    await waitFor(() => {
      const lastRequest = mock.history.get[mock.history.get.length - 1];
      expect(lastRequest.params).toMatchObject({ sort_by: 'name', sort_dir: 'desc' });
    });
  });
});
