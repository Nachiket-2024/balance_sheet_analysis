// Regression: LoginPage used to gate its entire render (including LoginForm)
// behind a shared OAuth2 loading flag that also toggled during the internal
// post-login profile fetch, causing the form to unmount for a full-page
// spinner and remount empty. These tests pin that the form stays mounted
// and interactive throughout a login attempt.
import type { ReactElement } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
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
      <ChakraProvider value={defaultSystem}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ChakraProvider>
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

    await userEvent.type(screen.getByPlaceholderText('Email'), 'user@example.com');
    await userEvent.type(screen.getByPlaceholderText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));

    // Mid-flight: inputs must still be in the DOM (the bug replaced them
    // with a full-page spinner here).
    expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
    expect(screen.queryByText('Signing you in...')).toBeNull();

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });
  });

  it('keeps whatever the user typed on screen if login ultimately fails', async () => {
    mock.onPost('/auth/login').reply(200, { message: 'Login successful' });
    // useLoginMutation treats a non-200 /auth/me after login as a failure
    // of the whole mutation (see useLoginMutation.ts).
    mock.onGet('/auth/me').reply(delayed([401, { detail: 'Not authenticated' }], 50));

    renderWithProviders(<LoginPage />);

    const emailInput = screen.getByPlaceholderText('Email') as HTMLInputElement;
    await userEvent.type(emailInput, 'user@example.com');
    await userEvent.type(screen.getByPlaceholderText('Password'), 'StrongPass123!');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(screen.queryByText(/not authenticated|failed|invalid|error/i)).toBeInTheDocument();
    });

    // Bug guarded against: unmounting LoginForm would reset its local
    // email/password state even though the user never cleared the form.
    expect((screen.getByPlaceholderText('Email') as HTMLInputElement).value).toBe(
      'user@example.com'
    );
  });
});
