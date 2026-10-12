import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import DashboardPage, { ACTIVE_SESSIONS_SECTION_ID } from '@/dashboard/DashboardPage';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

const testUser = {
  name: 'Test User',
  email: 'user@example.com',
  role: 'user',
  permissions: [],
  has_password: true,
  created_at: '2026-01-15T00:00:00Z',
  active_sessions: 2,
};

function loginEntry(id: number, eventType: string, createdAt: string) {
  return {
    id,
    user_email: testUser.email,
    event_type: eventType,
    success: true,
    ip_address: '203.0.113.7',
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
    request_id: null,
    event_metadata: null,
    created_at: createdAt,
  };
}

// usePreviousLoginQuery asks for each login event type separately, so the
// mock answers per event_type param.
function mockLogins(byEventType: Record<string, ReturnType<typeof loginEntry>[]>) {
  mock.onGet('/audit/security-log/me').reply((config) => [200, byEventType[config.params?.event_type] ?? []]);
}

// OperationsShortcutsCard's tiles gate on useCan, which reads permissions off
// this store - not off the /auth/me mock response directly (that only
// populates the store via useAuthSession, called at the app root, which
// these tests don't render). Same seeding pattern as
// rate_limits_page.test.tsx.
function seedPermissions(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Admin User',
    email: 'admin@example.com',
    role: 'admin',
    permissions,
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
    brand_color: null,
  });
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('shows a loading state before the current-user request resolves', () => {
    mock.onGet('/auth/me').reply(() => new Promise(() => {})); // never resolves
    renderDashboard();

    // role="status" is how screen readers pick up the loading skeleton
    // (see DashboardIdentityCardSkeleton).
    expect(screen.getByRole('status')).toHaveTextContent('Loading your details...');
  });

  it('renders the current user once GET /auth/me resolves', async () => {
    mock.onGet('/auth/me').reply(200, testUser);
    mock.onGet('/audit/security-log/me').reply(200, []);
    mock.onGet('/auth/sessions').reply(200, []);

    renderDashboard();

    expect(await screen.findByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
    expect(screen.getByText('user')).toBeInTheDocument();
    expect(screen.queryByText('Loading your details...')).toBeNull();
  });

  it('shows an error message when GET /auth/me fails', async () => {
    mock.onGet('/auth/me').reply(500);
    renderDashboard();

    expect(await screen.findByText('Unable to fetch user details')).toBeInTheDocument();
  });

  it('does not render a single-session Logout control (that lives in the app shell)', async () => {
    mock.onGet('/auth/me').reply(200, testUser);
    mock.onGet('/audit/security-log/me').reply(200, []);
    mock.onGet('/auth/sessions').reply(200, []);

    renderDashboard();

    await screen.findByText('Test User');
    expect(screen.queryByRole('button', { name: 'Logout' })).toBeNull();
  });

  it('shows the stats row and identity card shortcut buttons once the current user loads', async () => {
    mock.onGet('/auth/me').reply(200, testUser);
    mock.onGet('/audit/security-log/me').reply(200, []);
    mock.onGet('/auth/sessions').reply(200, []);

    renderDashboard();

    await screen.findByText('Test User');
    expect(screen.getByText('15 Jan 2026')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Active sessions')).toBeInTheDocument();
    // No Account Settings/Logout All buttons on the identity card: Account
    // Settings is one click away via the sidebar nav, and Logout All lives
    // on ActiveSessionsCard below, next to the rest of session management.
    expect(screen.queryByRole('button', { name: /Account Settings/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Logout All/i })).toBeNull();
    // The identity card's own shortcut buttons are always shown, no
    // permission required.
    expect(screen.getByRole('button', { name: /Change Password/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Appearance/i })).toBeInTheDocument();
  });

  describe('greeting subtitle', () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it.each([
      [9, 'Good morning, Test'],
      [14, 'Good afternoon, Test'],
      [21, 'Good evening, Test'],
    ])('at %i:30 local time says "%s" with the date', async (hour, greeting) => {
      // Only Date is faked, so axios/React Query timers keep running normally.
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date(2026, 0, 15, hour, 30));
      mock.onGet('/auth/me').reply(200, testUser);
      mock.onGet('/audit/security-log/me').reply(200, []);
      mock.onGet('/auth/sessions').reply(200, []);

      renderDashboard();

      await screen.findByText('Test User');
      expect(screen.getByText(new RegExp(`^${greeting} · Thursday,? 15 January 2026$`))).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument();
    });
  });

  describe('previous login stat', () => {
    it('shows the login before the most recent one, across password and Google logins', async () => {
      mock.onGet('/auth/me').reply(200, testUser);
      mock.onGet('/auth/sessions').reply(200, []);
      mockLogins({
        // Most recent overall is this visit's own login; the one before it
        // is a Google login, so both event types must be merged.
        login_success: [loginEntry(3, 'login_success', '2026-03-10T09:00:00Z'), loginEntry(1, 'login_success', '2026-02-01T09:00:00Z')],
        oauth2_login_success: [loginEntry(2, 'oauth2_login_success', '2026-03-05T09:00:00Z')],
      });

      renderDashboard();

      expect(await screen.findByText('Previous login')).toBeInTheDocument();
      expect(await screen.findByText('05 Mar 2026')).toBeInTheDocument();
      expect(screen.queryByText('10 Mar 2026')).toBeNull();
    });

    it('says there was none when the current login is the only one', async () => {
      mock.onGet('/auth/me').reply(200, testUser);
      mock.onGet('/auth/sessions').reply(200, []);
      mockLogins({ login_success: [loginEntry(1, 'login_success', '2026-03-10T09:00:00Z')] });

      renderDashboard();

      expect(await screen.findByText('None before this one')).toBeInTheDocument();
      expect(screen.queryByText('10 Mar 2026')).toBeNull();
    });
  });

  describe('active sessions stat', () => {
    const originalScrollIntoView = Element.prototype.scrollIntoView;

    afterEach(() => {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    });

    it('scrolls to and focuses the sessions card when clicked', async () => {
      // jsdom doesn't implement scrollIntoView.
      const scrollIntoView = vi.fn();
      Element.prototype.scrollIntoView = scrollIntoView;
      mock.onGet('/auth/me').reply(200, testUser);
      mock.onGet('/audit/security-log/me').reply(200, []);
      mock.onGet('/auth/sessions').reply(200, []);

      renderDashboard();

      const statButton = await screen.findByRole('button', { name: '2 active sessions, go to the sessions list' });
      await screen.findByText('Active Sessions');
      await userEvent.click(statButton);

      const section = document.getElementById(ACTIVE_SESSIONS_SECTION_ID);
      expect(section).not.toBeNull();
      expect(scrollIntoView).toHaveBeenCalledTimes(1);
      expect(scrollIntoView.mock.contexts[0]).toBe(section);
      expect(section).toHaveFocus();
      // Focus target only, not an extra tab stop.
      expect(section).toHaveAttribute('tabindex', '-1');
    });

    it('does not make the member since stat clickable', async () => {
      mock.onGet('/auth/me').reply(200, testUser);
      mock.onGet('/audit/security-log/me').reply(200, []);
      mock.onGet('/auth/sessions').reply(200, []);

      renderDashboard();

      const memberSince = await screen.findByText('15 Jan 2026');
      expect(memberSince.closest('button')).toBeNull();
    });
  });

  it('does not render the Operations shortcuts card for a viewer with no matching permissions', async () => {
    seedPermissions([]);
    mock.onGet('/auth/me').reply(200, testUser);
    mock.onGet('/audit/security-log/me').reply(200, []);
    mock.onGet('/auth/sessions').reply(200, []);

    renderDashboard();

    await screen.findByText('Test User');
    expect(screen.queryByText('Management')).toBeNull();
    expect(screen.queryByText('Operator Overview')).toBeNull();
  });

  it('shows a dash and "Couldn\'t load" on a tile whose count request fails', async () => {
    seedPermissions(['users:list_all']);
    mock.onGet('/auth/me').reply(200, { ...testUser, permissions: ['users:list_all'] });
    mock.onGet('/audit/security-log/me').reply(200, []);
    mock.onGet('/auth/sessions').reply(200, []);
    mock.onGet('/users/stats').reply(500);

    renderDashboard();

    expect(await screen.findByText("Couldn't load")).toBeInTheDocument();
    expect(screen.getByText('–')).toBeInTheDocument();
    // The normal caption is replaced, not shown alongside the error.
    expect(screen.queryByText(/unverified/)).toBeNull();
  });

  it('renders only the Management tiles matching the held permissions', async () => {
    seedPermissions(['users:list_all']);
    mock.onGet('/auth/me').reply(200, {
      name: 'Admin User',
      email: 'admin@example.com',
      role: 'admin',
      permissions: ['users:list_all'],
      has_password: true,
      created_at: '2026-01-15T00:00:00Z',
      active_sessions: 1,
    });
    mock.onGet('/audit/security-log/me').reply(200, []);
    mock.onGet('/auth/sessions').reply(200, []);
    mock.onGet('/users/stats').reply(200, { total: 42, verified: 40, unverified: 2, inactive: 1 });

    renderDashboard();

    await screen.findByText('Admin User');
    expect(await screen.findByRole('heading', { name: 'Management' })).toBeInTheDocument();
    expect(await screen.findByText('Users')).toBeInTheDocument();
    expect(await screen.findByText('42')).toBeInTheDocument();
    expect(screen.queryByText('Policies')).toBeNull();
    expect(screen.queryByText('Permissions')).toBeNull();
    expect(screen.queryByText('Rate Limits')).toBeNull();
    expect(screen.queryByText('Security Events')).toBeNull();
  });

  it('renders every permitted Management tile and handles each destination', async () => {
    const permissions = [
      'users:list_all',
      'policies:read',
      'permissions:read',
      'rate_limits:read',
      'security_audit:read',
    ];
    seedPermissions(permissions);
    mock.onGet('/auth/me').reply(200, { ...testUser, permissions });
    mock.onGet('/audit/security-log/me').reply(200, []);
    mock.onGet('/auth/sessions').reply(200, []);
    mock.onGet('/users/stats').reply(200, { total: 42, verified: 40, unverified: 2, inactive: 1 });
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/authorization/permissions/catalog').reply(200, [
      { action: 'users:read_any', resource_type: 'users', description: 'Read users.' },
    ]);
    mock.onGet('/rate-limits').reply(200, [], { 'x-total-count': '3' });

    renderDashboard();

    await screen.findByRole('heading', { name: 'Management' });
    for (const label of ['Users', 'Policies', 'Permissions', 'Rate Limits', 'Security Events']) {
      const tile = screen.getByRole('button', { name: new RegExp(label) });
      expect(tile).toBeInTheDocument();
      await userEvent.click(tile);
    }
  });
});
