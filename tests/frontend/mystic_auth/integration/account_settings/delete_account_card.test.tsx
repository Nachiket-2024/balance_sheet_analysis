import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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

async function openDangerTab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: 'Delete account' }));
}

describe('DeleteAccountCard', () => {
  beforeEach(() => {
    mock.reset();
    seedProfile();
    mock.onGet('/authorization/users/me/policies').reply(200, { policies: [] });
    mock.onGet('/authorization/users/me/permissions').reply(200, { permissions: [] });
  });

  it('requires the current password before confirming deletion when the account has one', async () => {
    renderAccountSettings();
    const user = userEvent.setup();

    await openDangerTab(user);
    await user.click(screen.getByRole('button', { name: 'Delete my account' }));

    expect(await screen.findByText(/enter your current password/i)).toBeInTheDocument();
    expect(mock.history.delete.length).toBe(0);
  });

  it('opens the confirm dialog and deletes the account, redirecting to login on success', async () => {
    mock.onDelete('/users/me').reply(200, { detail: 'Your account has been deleted' });

    renderAccountSettings();
    const user = userEvent.setup();

    await openDangerTab(user);
    await user.type(screen.getByPlaceholderText(/required to confirm this action/i), 'CurrentPass1');
    await user.click(screen.getByRole('button', { name: 'Delete my account' }));

    await screen.findByText('Delete your account?');
    await user.click(screen.getByRole('button', { name: 'Yes, delete my account' }));

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
    expect(JSON.parse(mock.history.delete[0].data)).toEqual({ current_password: 'CurrentPass1' });
    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(false));
  });

  it('shows an error and keeps the account when the delete request fails', async () => {
    mock.onDelete('/users/me').reply(500);

    renderAccountSettings();
    const user = userEvent.setup();

    await openDangerTab(user);
    await user.type(screen.getByPlaceholderText(/required to confirm this action/i), 'CurrentPass1');
    await user.click(screen.getByRole('button', { name: 'Delete my account' }));
    await screen.findByText('Delete your account?');
    await user.click(screen.getByRole('button', { name: 'Yes, delete my account' }));

    expect(await screen.findByText(/failed to delete account/i)).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('shows check-your-email messaging instead of deleting immediately for an OAuth-only account', async () => {
    seedProfile({ hasPassword: false });
    mock.onDelete('/users/me').reply(200, {
      detail: 'Check your email to confirm deleting your account',
      confirmation_required: true,
    });

    renderAccountSettings();
    const user = userEvent.setup();

    await openDangerTab(user);
    // OAuth-only account has no password field; the button opens the confirm dialog directly.
    await user.click(screen.getByRole('button', { name: 'Delete my account' }));
    await screen.findByText('Delete your account?');
    await user.click(screen.getByRole('button', { name: 'Send confirmation email' }));

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
    expect(await screen.findByText(/check your email/i)).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });
});
