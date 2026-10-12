import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import AccountSettingsPage from '@/account_settings/AccountSettingsPage';
import { useAuthStore } from '@/store/authStore';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seedProfile(overrides?: { hasPassword?: boolean }) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test User',
    email: 'user@example.com',
    role: 'user',
    permissions: ['users:read_own', 'users:update_own'],
    has_password: overrides?.hasPassword ?? true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
    brand_color: null,
  });
}

function renderAccountSettings() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AccountSettingsPage />
        </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AccountSettingsPage', () => {
  beforeEach(() => {
    mock.reset();
    seedProfile();
    mock.onGet('/authorization/users/me/policies').reply(200, {
      policies: [{ name: 'self_service', actions: ['users:read_own'], resource_type: 'users' }],
    });
    mock.onGet('/authorization/users/me/permissions').reply(200, { permissions: [] });
  });

  it("renders the caller's own editable name on the Profile tab", async () => {
    renderAccountSettings();

    // Email/role aren't shown here; DashboardPage already covers them read-only.
    expect(screen.getByDisplayValue('Test User')).toBeInTheDocument();
  });

  it('matches the User Access selected-state outline without the shared tab shadow', () => {
    renderAccountSettings();

    const profileTab = screen.getByRole('tab', { name: 'Profile' });
    expect(profileTab).toHaveClass('focus-visible:!border-transparent');
    expect(profileTab).toHaveClass('data-[state=active]:before:hidden');
    expect(profileTab).toHaveClass('dark:data-[state=active]:!border-transparent');
    expect(profileTab).toHaveClass('data-[state=active]:!shadow-[inset_0_0_0_2px_var(--brand-solid)]');
  });

  it('renders effective policies on the Permissions tab', async () => {
    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Permissions' }));
    // self_service now appears twice once its group is expanded by default:
    // the Policies badge, and again as the source tag on the effective-
    // permissions chip it granted.
    await screen.findAllByText('self_service');
  });

  it('renders the effective permissions (fanned-out policy actions and direct grants) and the raw direct grants, via the self-service /me endpoints', async () => {
    // Adds a direct grant on top of the shared mocks to prove both the
    // union (effective) and the raw-direct-only section reflect it.
    mock.onGet('/authorization/users/me/permissions').reply(200, {
      permissions: [{ action: 'policies:create', resource_type: 'policies' }],
    });

    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Permissions' }));

    // self_service now appears twice once its group is expanded by default:
    // the Policies badge, and again as the source tag on the effective-
    // permissions chip it granted.
    await screen.findAllByText('self_service');
    // Effective permissions include both the policy action and the direct grant.
    expect(screen.getByText('Read own users')).toBeInTheDocument();
    expect(screen.getAllByText('Create policies').length).toBeGreaterThanOrEqual(1);

    // Direct permissions show only the raw grant, not the policy-derived one.
    const directHeading = screen.getByText('Direct permissions');
    const directSection = directHeading.parentElement;
    expect(directSection).toBeTruthy();
    if (directSection) {
      expect(within(directSection).getByText('Create policies')).toBeInTheDocument();
      expect(within(directSection).queryByText('Read own users')).toBeNull();
    }
  });

  it('shows "Set" for an account with a password and "Not set" for an OAuth2-only account, on the Password tab', async () => {
    seedProfile({ hasPassword: false });
    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Password' }));

    expect(await screen.findByText('Not set')).toBeInTheDocument();
    expect(
      screen.getByText(/This account currently signs in with Google only/)
    ).toBeInTheDocument();
  });

  it('collapses a specific permission into its wildcard counterpart on the Permissions tab', async () => {
    // A direct grant on a specific resource_type is redundant once the same
    // action is already granted on "*"; only the wildcard badge should render.
    mock.onGet('/authorization/users/me/permissions').reply(200, {
      permissions: [
        { action: 'policies:read', resource_type: '*' },
        { action: 'policies:read', resource_type: 'policies' },
      ],
    });

    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Permissions' }));
    // self_service now appears twice once its group is expanded by default:
    // the Policies badge, and again as the source tag on the effective-
    // permissions chip it granted.
    await screen.findAllByText('self_service');

    expect(screen.getAllByText('All resource types').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('Policies')).toBeNull();
  });

  it('collapses a direct grant into a POLICY-sourced wildcard, not just another direct wildcard grant', async () => {
    // The covering wildcard here comes from an assigned policy, not another
    // direct grant; Direct permissions still has to drop the redundant grant.
    mock.onGet('/authorization/users/me/policies').reply(200, {
      policies: [
        { name: 'system_superuser', actions: ['permissions:grant'], resource_type: '*' },
      ],
    });
    mock.onGet('/authorization/users/me/permissions').reply(200, {
      permissions: [{ action: 'permissions:grant', resource_type: 'permissions' }],
    });

    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Permissions' }));
    // system_superuser appears twice once its group is expanded by default:
    // the Policies badge, and again as the source tag on the effective-
    // permissions chip it granted.
    await screen.findAllByText('system_superuser');

    const directHeading = screen.getByText('Direct permissions');
    const directSection = directHeading.parentElement;
    expect(directSection).toBeTruthy();
    if (directSection) {
      expect(within(directSection).queryByText('(permissions)')).toBeNull();
      expect(within(directSection).getByText(/no direct permissions/i)).toBeInTheDocument();
    }
  });

  it('submits a name change via PUT /users/me and reflects the update', async () => {
    mock.onPut('/users/me').reply(200, {
      id: 1,
      name: 'Updated Name',
      email: 'user@example.com',
      role: 'user',
      is_verified: true,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      deleted_at: null,
      has_password: true,
    });
    mock.onGet('/auth/me').reply(200, {
      name: 'Updated Name',
      email: 'user@example.com',
      role: 'user',
      permissions: ['users:read_own', 'users:update_own'],
      has_password: true,
    });

    renderAccountSettings();
    const user = userEvent.setup();

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'Updated Name');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mock.history.put.length).toBe(1);
    });
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ name: 'Updated Name' });
  });

  it('shows a local validation error and does not call the API for a weak new password', async () => {
    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Password' }));
    const passwordInput = screen.getByPlaceholderText(/leave blank to keep your current password/i);
    await user.type(passwordInput, 'weak');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    expect(mock.history.put.length).toBe(0);
  });

  it('requires the current password before submitting a new one for an account that already has one', async () => {
    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Password' }));
    const passwordInput = screen.getByPlaceholderText(/leave blank to keep your current password/i);
    await user.type(passwordInput, 'NewPassword1');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    expect(await screen.findByText(/enter your current password/i)).toBeInTheDocument();
    expect(mock.history.put.length).toBe(0);
  });

  it('sends current_password alongside password when changing an existing password', async () => {
    mock.onPut('/users/me').reply(200, {
      id: 1,
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      is_verified: true,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      deleted_at: null,
      has_password: true,
    });

    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Password' }));
    const passwordInput = screen.getByPlaceholderText(/leave blank to keep your current password/i);
    await user.type(passwordInput, 'NewPassword1');
    const currentPasswordInput = await screen.findByPlaceholderText(/required to confirm this change/i);
    await user.type(currentPasswordInput, 'OldPassword1');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({
      password: 'NewPassword1',
      current_password: 'OldPassword1',
    });
  });

  it('does not require or send current_password when setting a password for the first time (OAuth-only account)', async () => {
    seedProfile({ hasPassword: false });
    mock.onPut('/users/me').reply(200, {
      id: 1,
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      is_verified: true,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      deleted_at: null,
      has_password: true,
    });

    renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Password' }));
    const passwordInput = screen.getByPlaceholderText(/add a password so you can also sign in without google/i);
    await user.type(passwordInput, 'NewPassword1');
    await user.click(screen.getByRole('button', { name: /set password/i }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ password: 'NewPassword1' });
  });

  it('shows an error message when PUT /users/me fails', async () => {
    mock.onPut('/users/me').reply(500);

    renderAccountSettings();
    const user = userEvent.setup();

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'Another Name');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByText(/failed to update profile/i)).toBeInTheDocument();
  });
});
