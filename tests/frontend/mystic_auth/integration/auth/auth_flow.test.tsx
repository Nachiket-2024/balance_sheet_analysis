import type { ReactElement } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import LoginForm from '@/auth/login/LoginForm';
import LogoutButton from '@/auth/logout/LogoutButton';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('auth flow: login', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('successful login updates the auth store, shows the success message, and fires onSuccess', async () => {
    mock.onPost('/auth/login', { email: 'user@example.com', password: 'StrongPass123!' }).reply(200, {
      message: 'Login successful',
    });
    // Login success triggers a follow-up fetch of the fresh profile.
    mock.onGet('/auth/me').reply(200, { name: 'Test User', email: 'user@example.com', role: 'user', permissions: [] });

    const onSuccess = vi.fn();
    renderWithProviders(<LoginForm onSuccess={onSuccess} />);

    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    expect(await screen.findByText('Login successful!')).toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalledTimes(1);

    expect(mock.history.post.filter((r) => r.url === '/auth/login')).toHaveLength(1);
    expect(mock.history.get.filter((r) => r.url === '/auth/me')).toHaveLength(1);
  });

  it('failed login (wrong credentials) shows the error and never authenticates', async () => {
    mock.onPost('/auth/login').reply(401, { error: 'Invalid credentials or account locked' });

    const onSuccess = vi.fn();
    renderWithProviders(<LoginForm onSuccess={onSuccess} />);

    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument();

    expect(useAuthStore.getState().isAuthenticated).toBeNull();
    expect(onSuccess).toHaveBeenCalledTimes(0);
    expect(mock.history.get.filter((r) => r.url === '/auth/me')).toHaveLength(0);
  });

  it('moves focus to the login error so the recovery message is announced in context', async () => {
    mock.onPost('/auth/login').reply(401, { error: 'Invalid credentials or account locked' });

    renderWithProviders(<LoginForm />);
    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    const alert = await screen.findByRole('alert');
    expect(alert.parentElement).toHaveFocus();
  });

  it('shows a localized retry action after a network failure and preserves the entered credentials', async () => {
    mock.onPost('/auth/login').networkErrorOnce();
    mock.onPost('/auth/login').reply(200, { message: 'Login successful' });
    mock.onGet('/auth/me').reply(200, { name: 'Test User', email: 'user@example.com', role: 'user', permissions: [] });

    renderWithProviders(<LoginForm />);
    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByText("We couldn't connect. Check your connection and try again.")).toBeInTheDocument();
    const retryButton = await screen.findByRole('button', { name: 'Try again' });
    await userEvent.click(retryButton);

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });
    expect((screen.getByLabelText('Email') as HTMLInputElement).value).toBe('user@example.com');
    expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('StrongPass123!');
    expect(mock.history.post.filter((r) => r.url === '/auth/login')).toHaveLength(2);
  });

  it('failed login while account is locked (429) surfaces the lockout message', async () => {
    mock.onPost('/auth/login').reply(429, {
      error: 'Too many failed login attempts, account temporarily locked',
      code: 'ACCOUNT_LOCKED',
      params: { minutes: 1 },
    });

    renderWithProviders(<LoginForm />);

    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByText(/Too many failed login attempts/)).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBeNull();
  });

  // Regression (design review bug 6): the login button used to stay
  // clickable while the account was locked, even though the alert said
  // "Try again in N min". It must show disabled with a countdown instead.
  it('disables the button with a live countdown when the backend reports ACCOUNT_LOCKED', async () => {
    mock.onPost('/auth/login').reply(429, {
      error: 'Too many failed login attempts, account temporarily locked',
      code: 'ACCOUNT_LOCKED',
      params: { minutes: 1 },
    });

    renderWithProviders(<LoginForm />);

    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    const lockedButton = await screen.findByRole('button', { name: /try again in 1:00/i });
    expect(lockedButton).toBeDisabled();

    // A second click while locked must not fire another request.
    await userEvent.click(lockedButton);
    expect(mock.history.post.filter((r) => r.url === '/auth/login')).toHaveLength(1);
  });

  it('uses the backend Retry-After seconds for the lockout countdown', async () => {
    mock.onPost('/auth/login').reply(
      429,
      { error: 'Too many failed login attempts, account temporarily locked', code: 'ACCOUNT_LOCKED' },
      { 'Retry-After': '17' },
    );

    renderWithProviders(<LoginForm />);
    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('button', { name: /try again in 0:17/i })).toBeDisabled();
  });

  it('keeps the password visibility control keyboard reachable', async () => {
    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();
    const password = screen.getByLabelText('Password');
    const reveal = screen.getByRole('button', { name: 'Show password' });

    expect(reveal).not.toHaveAttribute('tabindex', '-1');
    password.focus();
    await user.tab();
    expect(reveal).toHaveFocus();
  });
});

describe('auth flow: logout', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('a successful backend logout surfaces as success and clears the auth store', async () => {
    mock.onPost('/auth/logout').reply(200, { message: 'Logged out successfully' });

    renderWithProviders(<LogoutButton />);

    await userEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(mock.history.post.filter((r) => r.url === '/auth/logout')).toHaveLength(1);
    });

    expect(await screen.findByText('Logged out successfully')).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().permissions).toEqual([]);
  });

  it('logout failure (no session) still clears the auth store and navigates away', async () => {
    // POST /auth/logout can 400 (e.g. an already-expired refresh token cookie).
    // Regression: that response used to leave the user stuck on the stale page
    // because cleanup/navigation only ran on mutation success. See
    // useLogoutMutation.ts's onSettled.
    mock.onPost('/auth/logout').reply(400, { error: 'No refresh token cookie found' });
    useAuthStore.setState({ ...initialAuthState, isAuthenticated: true });

    renderWithProviders(<LogoutButton />);

    await userEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });
});
