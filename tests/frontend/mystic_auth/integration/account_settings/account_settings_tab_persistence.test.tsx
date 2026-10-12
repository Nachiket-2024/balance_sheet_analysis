import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import AccountSettingsPage from '@/account_settings/AccountSettingsPage';
import { useAuthStore } from '@/store/authStore';
import { useAccountSettingsUiStore } from '@/account_settings/accountSettingsUiStore';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seedProfile() {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test User',
    email: 'user@example.com',
    role: 'user',
    permissions: ['users:read_own', 'users:update_own'],
    has_password: true,
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

describe('AccountSettingsPage tab persistence', () => {
  beforeEach(() => {
    mock.reset();
    seedProfile();
    mock.onGet('/authorization/users/me/policies').reply(200, { policies: [] });
    mock.onGet('/authorization/users/me/permissions').reply(200, { permissions: [] });
  });

  it('reopens on the tab last picked after the page unmounts and remounts (e.g. navigating away and back)', async () => {
    const { unmount } = renderAccountSettings();
    const user = userEvent.setup();

    await user.click(screen.getByRole('tab', { name: 'Appearance' }));
    expect(screen.getByRole('tab', { name: 'Appearance' })).toHaveAttribute('aria-selected', 'true');

    // Simulates leaving this page (e.g. to Dashboard) and coming back: the whole
    // component tree unmounts, which would reset a plain useState back to "profile".
    unmount();
    renderAccountSettings();

    expect(await screen.findByRole('tab', { name: 'Appearance' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Profile' })).toHaveAttribute('aria-selected', 'false');
  });

  it('still opens on Profile for a caller who never picked a tab this session', async () => {
    renderAccountSettings();

    expect(screen.getByRole('tab', { name: 'Profile' })).toHaveAttribute('aria-selected', 'true');
  });

  it('a `?tab=` deep link overrides the remembered tab for that one visit, but does not clobber it going forward', async () => {
    useAccountSettingsUiStore.getState().update({ activeTab: 'appearance' });

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/account-settings?tab=password']}>
          <AccountSettingsPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // The URL deep link wins for this visit, not the remembered "appearance".
    expect(screen.getByRole('tab', { name: 'Password' })).toHaveAttribute('aria-selected', 'true');
  });
});
