import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import ProfilePage from '@/profile/ProfilePage';
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
  });
}

function renderProfile() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={defaultSystem}>
        <MemoryRouter>
          <ProfilePage />
        </MemoryRouter>
      </ChakraProvider>
    </QueryClientProvider>
  );
}

describe('ProfilePage', () => {
  beforeEach(() => {
    mock.reset();
    seedProfile();
    mock.onGet('/authorization/users/me/policies').reply(200, {
      policies: [{ name: 'self_service' }],
    });
  });

  it("renders the caller's own name, email, and role from the auth store", async () => {
    renderProfile();

    expect(screen.getByDisplayValue('Test User')).toBeInTheDocument();
    expect(screen.getByDisplayValue('user@example.com')).toBeInTheDocument();
    await screen.findByText('self_service');
  });

  it('shows "Set" for an account with a password and "Not set" for an OAuth2-only account', async () => {
    seedProfile({ hasPassword: false });
    renderProfile();

    expect(await screen.findByText('Not set')).toBeInTheDocument();
    expect(
      screen.getByText(/This account currently signs in with Google only/)
    ).toBeInTheDocument();
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

    renderProfile();
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
    renderProfile();
    const user = userEvent.setup();

    const passwordInput = screen.getByPlaceholderText(/leave blank to keep your current password/i);
    await user.type(passwordInput, 'weak');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(mock.history.put.length).toBe(0);
  });

  it('requires the current password before submitting a new one for an account that already has one', async () => {
    renderProfile();
    const user = userEvent.setup();

    const passwordInput = screen.getByPlaceholderText(/leave blank to keep your current password/i);
    await user.type(passwordInput, 'NewPassword1');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

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

    renderProfile();
    const user = userEvent.setup();

    const passwordInput = screen.getByPlaceholderText(/leave blank to keep your current password/i);
    await user.type(passwordInput, 'NewPassword1');
    const currentPasswordInput = await screen.findByPlaceholderText(/required to confirm this change/i);
    await user.type(currentPasswordInput, 'OldPassword1');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

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

    renderProfile();
    const user = userEvent.setup();
    await screen.findByText('Not set');

    const passwordInput = screen.getByPlaceholderText(/add a password so you can also sign in without google/i);
    await user.type(passwordInput, 'NewPassword1');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ password: 'NewPassword1' });
  });

  it('shows an error message when PUT /users/me fails', async () => {
    mock.onPut('/users/me').reply(500);

    renderProfile();
    const user = userEvent.setup();

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'Another Name');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByText(/failed to update profile/i)).toBeInTheDocument();
  });
});
