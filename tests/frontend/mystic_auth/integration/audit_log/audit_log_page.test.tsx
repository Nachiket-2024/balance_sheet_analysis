import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import AuditLogPage from '@/audit_log/AuditLogPage';

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

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AuditLogPage />
        </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AuditLogPage', () => {
  beforeEach(() => {
    mock.reset();
    mock.onGet('/authorization/audit-log/me').reply(200, []);
    mock.onGet('/audit/security-log/me').reply(200, []);
  });

  it('hides "All users" for a caller with no admin audit permissions, in both categories', async () => {
    seed([]);
    renderPage();

    // Authorization decisions is the default category tab.
    expect(await screen.findByRole('tab', { name: 'My activity' })).toBeInTheDocument();
    expect(screen.getByTestId('audit-log-view-summary')).toHaveTextContent('Authorization decisions/My activity');
    expect(screen.queryByRole('tab', { name: 'All users' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    expect(await screen.findByRole('tab', { name: 'My activity' })).toBeInTheDocument();
    expect(screen.getByTestId('audit-log-view-summary')).toHaveTextContent('Security events/My activity');
    expect(screen.queryByRole('tab', { name: 'All users' })).not.toBeInTheDocument();
  });

  it('enables the "All users" tab for authorization decisions when the caller holds policies:read', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply(200, []);

    renderPage();

    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.getByRole('tab', { name: 'All users' })).toBeEnabled();
    expect(screen.getByTestId('audit-log-view-summary')).toHaveTextContent('Authorization decisions/My activity');

    await userEvent.click(screen.getByRole('tab', { name: 'All users' }));
    expect(screen.getByTestId('audit-log-view-summary')).toHaveTextContent('Authorization decisions/All users');

    // Security events is a separate category tab and shouldn't inherit
    // authorization's policies:read-gated "All users" tab.
    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.queryByRole('tab', { name: 'All users' })).not.toBeInTheDocument();
  });

  it('enables the "All users" tab in both categories when the caller holds policies:read and security_audit:read', async () => {
    seed(['policies:read', 'security_audit:read']);
    mock.onGet('/authorization/audit-log').reply(200, []);
    mock.onGet('/audit/security-log').reply(200, []);

    renderPage();

    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.getByRole('tab', { name: 'All users' })).toBeEnabled();

    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await screen.findByRole('tab', { name: 'My activity' });
    expect(screen.getByRole('tab', { name: 'All users' })).toBeEnabled();
  });

  it('explains a permission-race 403 instead of showing a generic load failure', async () => {
    seed(['policies:read', 'security_audit:read']);
    mock.onGet('/authorization/audit-log').reply(403);
    mock.onGet('/audit/security-log').reply(403);
    mock.onGet('/audit/security-log/login-trend').reply(403);

    renderPage();
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));
    expect(await screen.findByText(/This audit view is no longer available because your permission changed/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));
    expect(await screen.findAllByText(/This security view is no longer available because your permission changed/i)).toHaveLength(2);
  });

  it('shows numbered pages from X-Total-Count and fetches the next page on click', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply((config) => {
      const offset = Number(config.params?.offset ?? 0);
      if (offset === 0) {
        return [200, [{ id: 1, user_email: 'a@example.com', action: 'users:read_own', resource_type: 'users', resource_identifier: null, allowed: true, candidate_policy_names: [], granting_policy_names: [], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' }], { 'x-total-count': '30' }];
      }
      return [200, [{ id: 2, user_email: 'b@example.com', action: 'users:read_own', resource_type: 'users', resource_identifier: null, allowed: true, candidate_policy_names: [], granting_policy_names: [], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' }], { 'x-total-count': '30' }];
    });

    renderPage();
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));

    expect(await screen.findByText('a@example.com')).toBeInTheDocument();
    // 30 rows / 25 per page = 2 pages.
    const page2Buttons = screen.getAllByRole('button', { name: 'Page 2' });
    expect(page2Buttons.length).toBeGreaterThan(0);

    await userEvent.click(page2Buttons[0]);
    expect(await screen.findByText('b@example.com')).toBeInTheDocument();
  });

  it('opens the event details drawer on row click and closes it via the close button', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply(200, [
      { id: 1, user_email: 'a@example.com', action: 'users:read_own', resource_type: 'users', resource_identifier: null, allowed: true, candidate_policy_names: ['self_service'], granting_policy_names: ['self_service'], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' },
    ], { 'x-total-count': '1' });

    renderPage();
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));
    await screen.findByText('a@example.com');

    await userEvent.click(screen.getByText('a@example.com'));

    expect(await screen.findByText('Authorization decision')).toBeInTheDocument();
    expect(screen.getByText('1 of 1')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(screen.queryByText('Authorization decision')).toBeNull();
  });

  it('renders my authorization activity and applies the drawer action filter', async () => {
    seed([]);
    mock.onGet('/authorization/audit-log/me').reply(200, [
      { id: 4, user_email: 'user@example.com', action: 'users:read_own', resource_type: 'users', resource_identifier: null, allowed: true, candidate_policy_names: ['self_service'], granting_policy_names: ['self_service'], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' },
    ], { 'x-total-count': '1' });

    renderPage();
    await screen.findByText('user@example.com');
    await userEvent.click(screen.getByText('user@example.com'));

    expect(await screen.findByText('Authorization decision')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Only this action' }));
    expect(screen.getAllByText('Read own users').length).toBeGreaterThan(0);
  });

  it('renders my security activity and applies event and IP drawer filters', async () => {
    seed([]);
    mock.onGet('/audit/security-log/me').reply(200, [
      { id: 5, user_email: 'user@example.com', event_type: 'login_success', success: true, ip_address: '203.0.113.7', user_agent: 'Chrome', request_id: 'req-1', event_metadata: null, created_at: '2026-01-01T00:00:00Z' },
    ], { 'x-total-count': '1' });
    mock.onGet('/audit/security-log/me/login-trend').reply(200, []);

    renderPage();
    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await screen.findByText('user@example.com');
    await userEvent.click(screen.getByText('user@example.com'));

    expect(await screen.findByText('Security event')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Only this event' }));
    await userEvent.click(screen.getByText('user@example.com'));
    await userEvent.click(screen.getByRole('button', { name: 'Only this IP' }));
    expect(screen.getAllByText('203.0.113.7').length).toBeGreaterThan(0);
  });

  it('renders all security activity for a permitted caller and opens event details', async () => {
    seed(['security_audit:read']);
    mock.onGet('/audit/security-log').reply(200, [
      { id: 6, user_email: 'other@example.com', event_type: 'permission_granted', success: true, ip_address: '203.0.113.8', user_agent: 'Chrome', request_id: 'req-2', event_metadata: { granted_by: 'admin@example.com', action: 'users:read_any', resource_type: 'users' }, created_at: '2026-01-01T00:00:00Z' },
    ], { 'x-total-count': '1' });
    mock.onGet('/audit/security-log/login-trend').reply(200, []);

    renderPage();
    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));
    await screen.findByText('other@example.com');
    await userEvent.click(screen.getByText('other@example.com'));

    expect(await screen.findByText('Security event')).toBeInTheDocument();
    expect(screen.getByText('Access change')).toBeInTheDocument();
  });

  it('applies all security filters and clears the active IP filter', async () => {
    seed(['security_audit:read']);
    mock.onGet('/audit/security-log').reply(200, [], { 'x-total-count': '0' });
    mock.onGet('/audit/security-log/login-trend').reply(200, []);

    renderPage();
    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));

    const expandedIpInput = screen.getByRole('textbox', { name: 'Filter by IP address' });
    await userEvent.type(expandedIpInput, '203.0.113.99');
    await userEvent.click(screen.getByRole('button', { name: 'Filter by event' }));
    await userEvent.click(screen.getByText('Signed in'));

    const clearButtons = screen.getAllByRole('button', { name: 'Clear filters' });
    await userEvent.click(clearButtons[clearButtons.length - 1]);
  });

  it('shows the authorization search empty state and clears its filters', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply(200, [], { 'x-total-count': '0' });

    renderPage();
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));

    const searchInput = screen.getByRole('textbox', { name: 'Search by user email...' });
    await userEvent.type(searchInput, 'missing@example.com');
    expect(await screen.findByText('No authorization decisions match that search')).toBeInTheDocument();

    const authorizationClearButtons = screen.getAllByRole('button', { name: 'Clear filters' });
    await userEvent.click(authorizationClearButtons[authorizationClearButtons.length - 1]);
    expect(screen.queryByText('No authorization decisions match that search')).not.toBeInTheDocument();
  });

  it('shows the security filtered empty state and clears its filters', async () => {
    seed(['security_audit:read']);
    mock.onGet('/audit/security-log').reply(200, [], { 'x-total-count': '0' });
    mock.onGet('/audit/security-log/login-trend').reply(200, []);

    renderPage();
    await userEvent.click(screen.getByRole('tab', { name: 'Security events' }));
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));

    await userEvent.type(screen.getByRole('textbox', { name: 'Filter by IP address' }), '192.0.2.44');
    expect(await screen.findByText('No security events match these filters')).toBeInTheDocument();

    const securityClearButtons = screen.getAllByRole('button', { name: 'Clear filters' });
    await userEvent.click(securityClearButtons[securityClearButtons.length - 1]);
    expect(screen.queryByText('No security events match these filters')).not.toBeInTheDocument();
  });

  it('navigates between authorization entries in the details drawer', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/audit-log').reply(200, [
      { id: 7, user_email: 'first@example.com', action: 'users:read_own', resource_type: 'users', resource_identifier: null, allowed: true, candidate_policy_names: [], granting_policy_names: [], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' },
      { id: 8, user_email: 'second@example.com', action: 'users:read_any', resource_type: 'users', resource_identifier: null, allowed: false, candidate_policy_names: [], granting_policy_names: [], failed_conditions: null, context: null, created_at: '2026-01-01T00:00:00Z' },
    ], { 'x-total-count': '2' });

    renderPage();
    await userEvent.click(await screen.findByRole('tab', { name: 'All users' }));
    await userEvent.click(await screen.findByText('first@example.com'));
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getAllByText('second@example.com').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(screen.getAllByText('first@example.com').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Only this user' }));
    expect(screen.getByRole('textbox', { name: 'Search by user email...' })).toHaveValue('first@example.com');
  });
});
