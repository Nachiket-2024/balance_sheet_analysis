import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import PoliciesPage from '@/policies/PoliciesPage';

// Pagination, server-side search/filter/sort. Row actions (create/edit/
// delete) are covered in policies_page.test.tsx - split out the same way
// users_page_list_controls.test.tsx is split from users_page.test.tsx.

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test Admin',
    email: 'admin@example.com',
    role: 'admin',
    permissions,
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
    brand_color: null,
  });
}

function renderPage(initialEntries: string[] = ['/policies']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>
          <PoliciesPage />
        </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE_POLICIES = [
  {
    id: 1,
    name: 'self_service',
    description: 'Basic self-service access',
    actions: ['users:read_own'],
    resource_type: 'users',
    conditions: null,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    created_by: null,
  },
  {
    id: 2,
    name: 'policy_management',
    description: 'Manage policies',
    actions: ['policies:read'],
    resource_type: 'policies',
    conditions: null,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    created_by: null,
  },
];

describe('PoliciesPage list controls', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('shows numbered pages (from X-Total-Count) and fetches the next page on click', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      const offset = Number(config.params?.offset ?? 0);
      if (offset === 0) {
        return [200, SAMPLE_POLICIES, { 'x-total-count': '30' }];
      }
      return [
        200,
        [{ ...SAMPLE_POLICIES[0], id: 3, name: 'page_two_policy' }],
        { 'x-total-count': '30' },
      ];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('policy_management');
    // 30 policies / 25 per page = 2 pages, so page buttons should render.
    const page2Buttons = screen.getAllByRole('button', { name: 'Page 2' });
    expect(page2Buttons.length).toBeGreaterThan(0);

    await user.click(page2Buttons[0]);

    expect(await screen.findByText('page_two_policy')).toBeInTheDocument();
    const getRequests = mock.history.get.filter((r) => r.url === '/authorization/policies');
    expect(getRequests[getRequests.length - 1].params).toMatchObject({ offset: 25 });
  });

  it('searches server-side (debounced) and resets to page 1', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.search === 'administration') {
        return [200, [SAMPLE_POLICIES[1]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_POLICIES, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('self_service');
    await user.type(screen.getByPlaceholderText('Search by name or description...'), 'administration');

    // Debounced: the filtered result (and the self_service row disappearing)
    // shouldn't show up until after the debounce window.
    await waitFor(() => expect(screen.queryByText('self_service')).toBeNull(), { timeout: 2000 });
    expect(await screen.findByText('policy_management')).toBeInTheDocument();

    const lastRequest = mock.history.get[mock.history.get.length - 1];
    expect(lastRequest.params).toMatchObject({ search: 'administration' });
  });

  it('hydrates the policy search from a URL deep link without making other filters URL-backed', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.search === 'administration') {
        return [200, [SAMPLE_POLICIES[1]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_POLICIES, { 'x-total-count': '2' }];
    });

    renderPage(['/policies?search=administration']);

    expect(await screen.findByDisplayValue('administration')).toBeInTheDocument();
    expect(await screen.findByText('policy_management')).toBeInTheDocument();
    expect(screen.queryByText('self_service')).toBeNull();
    const listRequest = mock.history.get.find((request) => request.params?.limit === 25);
    expect(listRequest?.params).toMatchObject({ search: 'administration' });
  });

  it('regression: offers a fork-added resource type in the filter, not just the built-in ones', async () => {
    // .project/policies-design-review.md bug #1: the resource type filter
    // used to come from the fixed AUTHORIZATION_RESOURCE_TYPES constant, so
    // a fork-added type (e.g. "invoices") could never be selected even
    // though a real policy used it.
    seed(['policies:read']);
    const forkPolicy = { ...SAMPLE_POLICIES[0], id: 3, name: 'invoice_viewer', resource_type: 'invoices' };
    mock.onGet('/authorization/policies').reply(200, [...SAMPLE_POLICIES, forkPolicy]);

    renderPage();

    await screen.findByText('self_service');
    const select = screen.getByLabelText('Filter by resource type', { selector: 'select' }) as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);
    expect(optionValues).toContain('invoices');
  });

  it('filters by resource type via the select and resets to page 1', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.resource_type === 'policies') {
        return [200, [SAMPLE_POLICIES[1]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_POLICIES, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('self_service');
    await user.selectOptions(
      screen.getByLabelText('Filter by resource type', { selector: 'select' }),
      'policies'
    );

    await waitFor(() => expect(screen.queryByText('self_service')).toBeNull());
    expect(screen.getByText('policy_management')).toBeInTheDocument();

    const lastRequest = mock.history.get[mock.history.get.length - 1];
    expect(lastRequest.params).toMatchObject({ resource_type: 'policies' });
  });

  it('does not lose a destructive policy that is outside the current server page', async () => {
    seed(['policies:read']);
    const ordinaryPolicies = Array.from({ length: 25 }, (_, index) => ({
      ...SAMPLE_POLICIES[0],
      id: index + 1,
      name: `ordinary_policy_${index + 1}`,
    }));
    const destructivePolicy = {
      ...SAMPLE_POLICIES[0],
      id: 26,
      name: 'later_destructive_policy',
      actions: ['policies:delete'],
    };
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.destructive_only === true) {
        return [200, [destructivePolicy], { 'x-total-count': '1' }];
      }
      if (Number(config.params?.limit) === 1000) {
        return [200, [...ordinaryPolicies, destructivePolicy]];
      }
      return [200, ordinaryPolicies, { 'x-total-count': '26' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('ordinary_policy_1');
    await user.click(screen.getByRole('button', { name: 'Grant destructive actions' }));

    expect(await screen.findByText('later_destructive_policy')).toBeInTheDocument();
    expect(mock.history.get.at(-1)?.params).toMatchObject({ destructive_only: true });
    expect(screen.queryByRole('button', { name: 'Page 2' })).toBeNull();
  });

  it('filters by status via the select and resets to page 1', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.is_active === false) {
        return [200, [], { 'x-total-count': '0' }];
      }
      return [200, SAMPLE_POLICIES, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('self_service');
    await user.selectOptions(screen.getByLabelText('Filter by status', { selector: 'select' }), 'false');

    await waitFor(() => expect(screen.queryByText('self_service')).toBeNull());
    expect(await screen.findByText('No policies match these filters')).toBeInTheDocument();

    const lastRequest = mock.history.get[mock.history.get.length - 1];
    expect(lastRequest.params).toMatchObject({ is_active: false });
  });

  it('always requests the list sorted by name ascending (no column-header sort control in the card list)', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES, { 'x-total-count': '2' });

    renderPage();

    await screen.findByText('self_service');

    const listRequest = mock.history.get.find((r) => r.params?.offset === 0 && r.params?.limit === 25);
    expect(listRequest?.params).toMatchObject({ sort_by: 'name', sort_dir: 'asc' });
  });

  it('filters by contains-action via the grouped picker and resets to page 1', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.contains_action === 'policies:read') {
        return [200, [SAMPLE_POLICIES[1]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_POLICIES, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('self_service');
    await user.click(screen.getByRole('button', { name: 'Filter by action' }));
    await user.click(screen.getByText('Read policies'));

    await waitFor(() => expect(screen.queryByText('self_service')).toBeNull());
    expect(screen.getByText('policy_management')).toBeInTheDocument();

    const lastRequest = mock.history.get[mock.history.get.length - 1];
    expect(lastRequest.params).toMatchObject({ contains_action: 'policies:read' });
  });

  it('groups the built-in policies "Clear filters" reset to include contains-action', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.contains_action === 'policies:read') {
        return [200, [SAMPLE_POLICIES[1]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_POLICIES, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('self_service');
    await user.click(screen.getByRole('button', { name: 'Filter by action' }));
    await user.click(screen.getByText('Read policies'));

    const clearButton = await screen.findByRole('button', { name: /^Clear filters \(/ });
    await user.click(clearButton);

    expect(await screen.findByText('self_service')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Clear filters/ })).not.toBeInTheDocument();
  });

  it('always groups cards under resource-type headers', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES, { 'x-total-count': '2' });

    renderPage();
    await screen.findByText('self_service');
    expect(await screen.findByText('Users (1)')).toBeInTheDocument();
    expect(screen.getByText('Policies (1)')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: 'Group by resource type' })).not.toBeInTheDocument();
  });

  it('clears search, resource type and status filters when Clear filters is clicked', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      if (config.params?.search === 'administration') {
        return [200, [SAMPLE_POLICIES[1]], { 'x-total-count': '1' }];
      }
      return [200, SAMPLE_POLICIES, { 'x-total-count': '2' }];
    });

    renderPage();
    const user = userEvent.setup();

    await screen.findByText('self_service');
    expect(screen.queryByRole('button', { name: /Clear filters/ })).not.toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('Search by name or description...'), 'administration');
    await waitFor(() => expect(screen.queryByText('self_service')).toBeNull(), { timeout: 2000 });
    const clearButton = await screen.findByRole('button', { name: /^Clear filters \(/ });

    await user.click(clearButton);

    expect(await screen.findByText('self_service')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search by name or description...')).toHaveValue('');
    expect(screen.queryByRole('button', { name: /Clear filters/ })).not.toBeInTheDocument();
  });
});
