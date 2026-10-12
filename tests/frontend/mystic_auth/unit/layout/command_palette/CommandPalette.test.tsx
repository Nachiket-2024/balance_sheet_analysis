import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

const navigateMock = vi.fn();

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return { ...actual, useNavigate: () => navigateMock };
});

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import CommandPalette from '@/layout/command_palette/CommandPalette';

const mock = new MockAdapter(api);

const initialAuthState = useAuthStore.getState();

function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test User',
    email: 'user@example.com',
    role: 'user',
    permissions,
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
    brand_color: null,
  });
}

function renderPalette(onClose = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CommandPalette isOpen onClose={onClose} />
        </MemoryRouter>
    </QueryClientProvider>
  );
  return { ...utils, onClose };
}

describe('CommandPalette', () => {
  beforeEach(() => {
    navigateMock.mockClear();
    mock.reset();
    mock.onGet('/users/').reply(200, []);
    seed([]);
  });

  it('does not expose or request policy records without policies:read', async () => {
    renderPalette();

    await userEvent.type(screen.getByRole('textbox'), 'report');
    await waitFor(() => expect(screen.getByText('No matching results')).toBeInTheDocument());

    expect(mock.history.get.some((request) => request.url === '/authorization/policies')).toBe(false);
    expect(screen.queryByText('report_viewer')).toBeNull();
  });

  it('searches policy records for an authorized caller and navigates with a policy filter', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply((config) => {
      expect(config.params).toMatchObject({
        limit: 5,
        offset: 0,
        search: 'report',
        sort_by: 'name',
        sort_dir: 'asc',
      });
      return [200, [{
        name: 'report_viewer',
        description: 'Read-only reporting policy',
        resource_type: 'report',
        actions: ['read'],
        is_active: true,
        is_system: false,
      }], { 'x-total-count': '1' }];
    });

    const { onClose } = renderPalette();
    await userEvent.type(screen.getByRole('textbox'), 'report');

    await waitFor(() => expect(screen.getByText('report_viewer')).toBeInTheDocument());

    await userEvent.click(screen.getByText('report_viewer'));
    expect(navigateMock).toHaveBeenCalledWith('/policies?search=report_viewer');
    expect(onClose).toHaveBeenCalled();
  });

  it('lists only nav items requiring no permission for a caller with none', () => {
    renderPalette();

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Audit Log')).toBeInTheDocument();
    expect(screen.getByText('Account Settings')).toBeInTheDocument();
    expect(screen.queryByText('Users')).toBeNull();
    expect(screen.queryByText('Policies')).toBeNull();
  });

  it('includes permission-gated items once the caller holds the matching permission', () => {
    seed(['users:list_all', 'policies:read']);
    renderPalette();

    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Policies')).toBeInTheDocument();
  });

  it('filters the list by the search query, case-insensitively', async () => {
    renderPalette();

    await userEvent.type(screen.getByRole('textbox'), 'dash');

    await waitFor(() => expect(screen.queryByText('Audit Log')).toBeNull());
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThan(0);
    expect(screen.queryByText('Account Settings')).toBeNull();
  });

  it('shows a no-results message when the query matches nothing', async () => {
    renderPalette();

    await userEvent.type(screen.getByRole('textbox'), 'zzzzzzzzzz');

    await waitFor(() => expect(screen.getByText('No matching results')).toBeInTheDocument());
  });

  it('navigates to the highlighted item and closes on Enter, without arrow keys', async () => {
    const { onClose } = renderPalette();

    await userEvent.type(screen.getByRole('textbox'), '{Enter}');

    expect(navigateMock).toHaveBeenCalledWith('/dashboard');
    expect(onClose).toHaveBeenCalled();
  });

  it('moves the active selection down with ArrowDown and navigates to it on Enter', async () => {
    const { onClose } = renderPalette();

    const input = screen.getByRole('textbox');
    await userEvent.type(input, '{ArrowDown}{Enter}');

    expect(navigateMock).toHaveBeenCalledWith('/audit-log');
    expect(onClose).toHaveBeenCalled();
  });

  it('wraps back to the first item with ArrowUp from the first selection', async () => {
    const { onClose } = renderPalette();

    const input = screen.getByRole('textbox');
    // Dashboard(0) -> ArrowUp wraps to the last item, Account Settings.
    await userEvent.type(input, '{ArrowUp}{Enter}');

    expect(navigateMock).toHaveBeenCalledWith('/account-settings');
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when Escape is pressed (Dialog default close behavior)', async () => {
    const onClose = vi.fn();
    renderPalette(onClose);

    await userEvent.type(screen.getByRole('textbox'), '{Escape}');

    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when a result is clicked', async () => {
    const onClose = vi.fn();
    renderPalette(onClose);

    await userEvent.click(screen.getByText('Dashboard'));

    expect(navigateMock).toHaveBeenCalledWith('/dashboard');
    expect(onClose).toHaveBeenCalled();
  });

  it('surfaces every matching piece of page copy, not just titles, under a "Matching text" group', async () => {
    renderPalette();

    // "sessions" isn't a nav label, but real copy on the Dashboard's Active
    // Sessions card (ActiveSessionsCard).
    await userEvent.type(screen.getByRole('textbox'), 'sessions');

    await waitFor(() => expect(screen.getByText('Matching text')).toBeInTheDocument());
    expect(screen.getAllByText('Active Sessions').length).toBeGreaterThan(0);
  });

  it('shows one row per distinct matching string, not one collapsed row per page', async () => {
    renderPalette();

    // "password" matches multiple distinct strings on the Change Password
    // tab (e.g. "Change password", "Current password"), each its own row.
    await userEvent.type(screen.getByRole('textbox'), 'password');

    await waitFor(() => expect(screen.getAllByText('Change password').length).toBeGreaterThan(0));
    expect(screen.getAllByText('Current password').length).toBeGreaterThan(0);
  });

  it('navigates to a matched string\'s destination when clicked', async () => {
    const { onClose } = renderPalette();

    await userEvent.type(screen.getByRole('textbox'), 'sessions');
    await waitFor(() => expect(screen.getAllByText('Active Sessions').length).toBeGreaterThan(0));
    const [firstMatch] = screen.getAllByText('Active Sessions');
    await userEvent.click(firstMatch);

    expect(navigateMock).toHaveBeenCalledWith(expect.stringContaining('/dashboard'));
    expect(onClose).toHaveBeenCalled();
  });
});
