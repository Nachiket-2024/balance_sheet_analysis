// Regression: LoginPage used to gate its whole render behind a shared OAuth2
// loading flag that also toggled during the post-login profile fetch, so the
// form unmounted for a full-page spinner and remounted empty. These tests
// check the form stays mounted and interactive through a login attempt.
import type { ReactElement } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import LoginPage from '@/auth/login/LoginPage';

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

function delayed<T>(value: [number, T], ms: number) {
  return () => new Promise<[number, T]>((resolve) => setTimeout(() => resolve(value), ms));
}

describe('LoginPage stays on the login form throughout a login attempt', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('does not unmount LoginForm while the post-login profile fetch is in flight', async () => {
    mock.onPost('/auth/login').reply(200, { message: 'Login successful' });
    // Deliberately slow so the test can observe the in-flight state.
    mock
      .onGet('/auth/me')
      .reply(delayed([200, { name: 'Test User', email: 'user@example.com', role: 'user', permissions: [] }], 100));

    renderWithProviders(<LoginPage />);

    await userEvent.type(screen.getByLabelText('Email'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    // Mid-flight: inputs must still be in the DOM, not replaced by a spinner.
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.queryByText('Signing you in...')).toBeNull();

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });
  });

  it('keeps whatever the user typed on screen if login ultimately fails', async () => {
    mock.onPost('/auth/login').reply(200, { message: 'Login successful' });
    // A non-200 /auth/me after login fails the whole mutation (see useLoginMutation.ts).
    mock.onGet('/auth/me').reply(delayed([401, { detail: 'Not authenticated' }], 50));

    renderWithProviders(<LoginPage />);

    const emailInput = screen.getByLabelText('Email') as HTMLInputElement;
    await userEvent.type(emailInput, 'user@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    await waitFor(() => {
      expect(screen.queryByText(/not authenticated|failed|invalid|error/i)).toBeInTheDocument();
    });

    // Unmounting LoginForm would reset its typed-in state; it shouldn't unmount here.
    expect((screen.getByLabelText('Email') as HTMLInputElement).value).toBe(
      'user@example.com'
    );
  });
});
