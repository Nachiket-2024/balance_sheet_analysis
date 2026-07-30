import type { ReactElement } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import LoginForm from '@/auth/login/LoginForm';
import LogoutButton from '@/auth/logout/LogoutButton';
import LogoutAllButton from '@/auth/logout_all/LogoutAllButton';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={defaultSystem}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ChakraProvider>
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
    // useLoginMutation calls getCurrentUserApi once to fetch the fresh profile.
    mock.onGet('/auth/me').reply(200, { name: 'Test User', email: 'user@example.com', role: 'user', permissions: [] });

    const onSuccess = vi.fn();
    renderWithProviders(<LoginForm onSuccess={onSuccess} />);

    await userEvent.type(screen.getByPlaceholderText('Email'), 'user@example.com');
    await userEvent.type(screen.getByPlaceholderText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    expect(await screen.findByText('Login successful!')).toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalledTimes(1);

    // Both the login call and the profile fetch actually went out.
    expect(mock.history.post.filter((r) => r.url === '/auth/login')).toHaveLength(1);
    expect(mock.history.get.filter((r) => r.url === '/auth/me')).toHaveLength(1);
  });

  it('failed login (wrong credentials) shows the error and never authenticates', async () => {
    mock.onPost('/auth/login').reply(401, { error: 'Invalid credentials or account locked' });

    const onSuccess = vi.fn();
    renderWithProviders(<LoginForm onSuccess={onSuccess} />);

    await userEvent.type(screen.getByPlaceholderText('Email'), 'user@example.com');
    await userEvent.type(screen.getByPlaceholderText('Password'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));

    expect(await screen.findByText('Invalid credentials or account locked')).toBeInTheDocument();

    expect(useAuthStore.getState().isAuthenticated).toBeNull(); // never touched by a failed login attempt
    expect(onSuccess).toHaveBeenCalledTimes(0);
    // /auth/me must never be called if the login call itself failed.
    expect(mock.history.get.filter((r) => r.url === '/auth/me')).toHaveLength(0);
  });

  it('failed login while account is locked (429) surfaces the lockout message', async () => {
    mock.onPost('/auth/login').reply(429, { error: 'Too many failed login attempts, account temporarily locked' });

    renderWithProviders(<LoginForm />);

    await userEvent.type(screen.getByPlaceholderText('Email'), 'user@example.com');
    await userEvent.type(screen.getByPlaceholderText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));

    expect(await screen.findByText('Too many failed login attempts, account temporarily locked')).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBeNull();
  });

  it('Clear button resets both the form inputs and the login mutation state', async () => {
    mock.onPost('/auth/login').reply(401, { error: 'Invalid credentials or account locked' });

    renderWithProviders(<LoginForm />);

    const emailInput = screen.getByPlaceholderText('Email') as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText('Password') as HTMLInputElement;

    await userEvent.type(emailInput, 'user@example.com');
    await userEvent.type(passwordInput, 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));
    expect(await screen.findByText('Invalid credentials or account locked')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(emailInput.value).toBe('');
    expect(passwordInput.value).toBe('');
    expect(screen.queryByText('Invalid credentials or account locked')).toBeNull();
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

  it('logout failure (no session) surfaces the error without crashing', async () => {
    mock.onPost('/auth/logout').reply(400, { error: 'No refresh token cookie found' });

    renderWithProviders(<LogoutButton />);

    await userEvent.click(screen.getByRole('button', { name: 'Logout' }));

    expect(await screen.findByText('No refresh token cookie found')).toBeInTheDocument();
  });
});

describe('auth flow: logout all devices', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('a successful backend logout-all surfaces as success and clears the auth store', async () => {
    mock.onPost('/auth/logout/all').reply(200, { message: 'Logged out from 3 devices' });

    renderWithProviders(<LogoutAllButton />);

    // Ends every session on every device, so it's confirm-gated : see
    // LogoutAllButton.tsx.
    await userEvent.click(screen.getByRole('button', { name: 'Logout All Devices' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Logout all' }));

    await waitFor(() => {
      expect(mock.history.post.filter((r) => r.url === '/auth/logout/all')).toHaveLength(1);
    });

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
    expect(screen.queryByText('Logout all devices failed')).toBeNull();
  });

  it('logout-all failure surfaces the error without crashing', async () => {
    mock.onPost('/auth/logout/all').reply(400, { error: 'No refresh token cookie found' });

    renderWithProviders(<LogoutAllButton />);

    await userEvent.click(screen.getByRole('button', { name: 'Logout All Devices' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Logout all' }));

    expect(await screen.findByText('No refresh token cookie found')).toBeInTheDocument();
  });
});
